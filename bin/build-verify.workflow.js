export const meta = {
  name: 'direttore-build-verify',
  description: 'Build every unit in its own worktree and check each delivery with a different model; one correction after a KO',
  whenToUse: 'Called by the direttore skill with engine claude or mixed; not meant to be run by hand.',
  phases: [
    { title: 'Build', detail: 'one builder per unit, each in its own worktree' },
    { title: 'Verify', detail: 'a different model checks each delivery as it arrives' },
    { title: 'Correct', detail: 'one correction by the builder after a KO, then a new check' },
  ],
}

// args (see skills/direttore/references/engines.md):
//   plugin   absolute path of the plugin
//   repo     absolute path of the checkout the run started in (it sits on the base head)
//   base     base SHA every unit starts from
//   engine   "claude" | "mixed"
//   context  text of .orchestratore/CONTEXT.md
//   units    [{ id, tier, brief }]   tier = 1, 2 or 3; brief = text of .orchestratore/briefs/<ID>.md
//   models   { builder, verifier, codex_unit_verifier }
const { plugin, repo, base, engine, context, units, models } = args

if (engine !== 'claude' && engine !== 'mixed') {
  throw new Error('engine must be "claude" or "mixed"; the codex engine does not use this workflow')
}
if (!models || !models.builder || !models.verifier || models.builder === models.verifier) {
  throw new Error('models.builder and models.verifier are required and must differ')
}
if (engine === 'mixed' && !models.codex_unit_verifier) {
  throw new Error('engine "mixed" needs models.codex_unit_verifier')
}

const BUILT = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['done', 'blocked', 'failed'] },
    worktree: { type: 'string', description: 'absolute path of the worktree' },
    branch: { type: 'string' },
    hash: { type: 'string', description: 'full output of git rev-parse HEAD' },
    files: { type: 'string' },
    commands: { type: 'string', description: 'one "<command> → exit <code>" per line' },
    blockers: { type: 'string' },
  },
  required: ['status', 'worktree', 'branch', 'hash', 'files', 'commands', 'blockers'],
}

const VERDICT = {
  type: 'object',
  properties: {
    result: { type: 'string', enum: ['OK', 'KO', 'BLOCKED'] },
    verdict: { type: 'string', description: 'the full fixed-format verdict, verbatim' },
    verdict_file: { type: 'string', description: 'path of the verdict file, or "none"' },
  },
  required: ['result', 'verdict', 'verdict_file'],
}

// Values that end up inside a shell command or a file name are checked first: a builder's
// report is model output, never trusted text.
const SAFE_PATH = /^\/[\p{L}\p{N}._\/@+ -]+$/u
const SAFE_ID = /^[A-Za-z0-9][A-Za-z0-9._-]*$/
const SHA = /^[0-9a-f]{40,64}$/

for (const [name, value] of [['plugin', plugin], ['repo', repo]]) {
  if (typeof value !== 'string' || !SAFE_PATH.test(value) || value.includes('..')) {
    throw new Error(`${name} must be an absolute path without shell metacharacters`)
  }
}
if (typeof base !== 'string' || !SHA.test(base)) throw new Error('base must be a full commit SHA')
if (!Array.isArray(units) || units.length === 0) throw new Error('units must be a non-empty list')
for (const unit of units) {
  if (!unit || typeof unit.id !== 'string' || !SAFE_ID.test(unit.id) || typeof unit.brief !== 'string') {
    throw new Error('every unit needs an id (letters, digits, . _ -) and its brief text')
  }
  // A tier that is not plainly 1, 2 or 3 must never fall to the economical check.
  if (![1, 2, 3].includes(unit.tier) && !['1', '2', '3'].includes(unit.tier)) {
    throw new Error(`unit ${unit.id}: tier must be 1, 2 or 3`)
  }
}
// Only the models this engine uses: an empty key the engine never reads is not an error.
const usedModels = [models.builder, models.verifier]
if (engine === 'mixed') usedModels.push(models.codex_unit_verifier)
for (const model of usedModels) {
  if (typeof model !== 'string' || !/^[A-Za-z0-9._:\/-]+$/.test(model)) {
    throw new Error('model names may hold only letters, digits and . _ : / -')
  }
}

// A delivery counts only with a committed hash and a worktree path that are safe to use.
function delivered(built) {
  return Boolean(
    built &&
      built.status === 'done' &&
      typeof built.hash === 'string' &&
      SHA.test(built.hash) &&
      typeof built.worktree === 'string' &&
      SAFE_PATH.test(built.worktree) &&
      !built.worktree.includes('..'),
  )
}

// The check of one delivery. Tier 3, and every unit of the claude engine, goes to the
// strong verifier agent. In the mixed engine a tier 1-2 unit is checked by Codex: a relay
// agent only runs the command and hands back the file Codex wrote.
function verify(unit, built, round) {
  const where = `worktree: ${built.worktree}  hash: ${built.hash}  base: ${base}`
  if (engine === 'claude' || Number(unit.tier) >= 3) {
    return agent(`${where}\n\n${context}\n\n${unit.brief}`, {
      label: `verify:${unit.id}`,
      phase: round === 1 ? 'Verify' : 'Correct',
      agentType: 'direttore:verifier',
      model: models.verifier,
      schema: VERDICT,
    }).then(v => (v ? { ...v, verdict_file: 'none', verifier: models.verifier } : null))
  }
  const dir = `${repo}/.orchestratore/briefs/verify`
  const name = `${unit.id}.r${round}`
  return agent(
    `You relay a check done by another program. Do not review the code yourself and do not ` +
      `change any file except the one named in step 1.\n\n` +
      `1. cp "${dir}/${unit.id}.md" "${dir}/${name}.md" && printf '\\n%s\\n' ` +
      `"${where}" >> "${dir}/${name}.md"\n` +
      `2. bash "${plugin}/bin/codex-task.sh" --model "${models.codex_unit_verifier}" --effort low ` +
      `verify "${built.worktree}" "${dir}/${name}.md"   (it may take minutes: wait for it)\n` +
      `3. Read "${dir}/${name}.verify.last.md".\n\n` +
      `Return: result = the value of its "result:" line; verdict = the file content, verbatim; ` +
      `verdict_file = "${dir}/${name}.verify.last.md". If step 2 exits non-zero or the file is ` +
      `missing, return result BLOCKED and put the command output in verdict.`,
    {
      label: `verify:${unit.id}`,
      phase: round === 1 ? 'Verify' : 'Correct',
      model: models.builder,
      effort: 'low',
      schema: VERDICT,
    },
  ).then(v => (v ? { ...v, verifier: models.codex_unit_verifier } : null))
}

const results = await pipeline(
  units,
  // Build: one builder per unit, in its own worktree cut from the checkout (the base head).
  async unit => {
    const built = await agent(`${context}\n\n${unit.brief}`, {
      label: `build:${unit.id}`,
      phase: 'Build',
      agentType: 'direttore:builder',
      model: models.builder,
      isolation: 'worktree',
      schema: BUILT,
    })
    return { id: unit.id, built, verdicts: [] }
  },
  // Verify on arrival: no barrier, a fast unit is checked while the others still build.
  async (state, unit) => {
    if (!delivered(state.built)) return state
    const verdict = await verify(unit, state.built, 1)
    return { ...state, verdicts: [verdict] }
  },
  // Correct: a KO goes back to a builder once, in the same worktree, then a new check.
  async (state, unit) => {
    const first = state.verdicts[0]
    if (!first || first.result !== 'KO') return state
    const fixed = await agent(
      `workdir: ${state.built.worktree}\n\n${context}\n\n${unit.brief}\n\n` +
        `Your first delivery (${state.built.hash}) failed its check. Fix exactly these ` +
        `findings. Work only inside the workdir above (cd there first; every edit and ` +
        `command stays in it, on its branch), then commit:\n\n${first.verdict}`,
      {
        label: `fix:${unit.id}`,
        phase: 'Correct',
        agentType: 'direttore:builder',
        model: models.builder,
        schema: BUILT,
      },
    )
    // A correction that is missing, or that landed anywhere but the unit's worktree, is
    // not a delivery.
    if (!delivered(fixed) || fixed.worktree !== state.built.worktree) {
      return { ...state, correction: fixed || null, correction_missing: true }
    }
    const second = await verify(unit, fixed, 2)
    return { ...state, first_hash: state.built.hash, built: fixed, verdicts: [first, second] }
  },
)

// One entry per unit, in the order given. `state` is what the director writes in RUN.md;
// every verdict still has to pass bin/verdict-check.py before it counts.
return units.map((unit, i) => {
  const r = results[i]
  if (!r) return { id: unit.id, state: 'failed', reason: 'a stage threw; see the workflow log' }
  if (!delivered(r.built)) {
    return { id: unit.id, state: 'not delivered', built: r.built || null }
  }
  const last = r.verdicts[r.verdicts.length - 1]
  const ko = r.verdicts.filter(v => v && v.result === 'KO').length
  // verified | blocked | second KO | correction missing | unverified
  let state = 'unverified' // a check that returned nothing: `built` is still to be checked
  if (r.correction_missing) state = 'correction missing'
  else if (last && last.result === 'OK') state = 'verified'
  else if (last && last.result === 'BLOCKED') state = 'blocked'
  else if (ko >= 2) state = 'second KO'
  return {
    id: unit.id, state, ko, built: r.built, first_hash: r.first_hash || null,
    correction: r.correction || null, verdicts: r.verdicts,
  }
})
