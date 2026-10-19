#!/usr/bin/env node
/**
 * mcode-team-builder — deterministic part of the team build, from the terminal.
 *
 *   mcode-team-builder --blueprint team.json              # scaffold + validate
 *   mcode-team-builder --blueprint team.json --dry-run    # plan only
 *   mcode-team-builder --init                            # write a starter blueprint
 *
 * This covers the reproducible half: blueprint -> agent.md files -> validation.
 * The interactive half (native registration, avatars, the orchestrator roster,
 * warm-up) is what the MiniMax Code skill does in chat.
 */
'use strict';

const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.resolve(__dirname, '..');
const SCRIPTS = path.join(ROOT, 'minimax-code-team-builder', 'scripts');

function pythonCommand() {
  for (const cmd of ['python', 'python3', 'py']) {
    const probe = spawnSync(cmd, ['-c', 'import sys; print(sys.version_info[0])'], {
      encoding: 'utf8',
    });
    if (probe.status === 0) return cmd;
  }
  return null;
}

function runPython(cmd, args) {
  const res = spawnSync(cmd, args, { stdio: 'inherit' });
  return res.status === null ? 1 : res.status;
}

function usage() {
  console.log(`mcode-team-builder — build a collaborating MiniMax Code subagent team

Usage:
  mcode-team-builder --blueprint <team.json> [--data-dir <dir>] [--dry-run]
  mcode-team-builder --init [dir]
  mcode-team-builder --help

Options:
  --blueprint <path>  Team blueprint JSON (see examples/team.example.json)
  --data-dir <path>   MCode data directory — the folder containing agents/
                      (default: $MINIMAX_DATA_DIR / $MAVIS_DATA_DIR / ~/.minimax)
  --dry-run           Show the plan, write nothing
  --init [dir]        Write a starter blueprint (default: ./team.json)

Examples:
  mcode-team-builder --blueprint team.json
  npx github:DF-Guan/minimax-code-team-builder --blueprint team.json
`);
}

function parseArgs(argv) {
  const opts = { blueprint: null, dataDir: null, dryRun: false, init: false, initDir: null };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--blueprint' || arg === '-b') opts.blueprint = argv[++i];
    else if (arg === '--data-dir' || arg === '-d') opts.dataDir = argv[++i];
    else if (arg === '--dry-run') opts.dryRun = true;
    else if (arg === '--init') {
      opts.init = true;
      const next = argv[i + 1];
      if (next && !next.startsWith('-')) { opts.initDir = next; i += 1; }
    } else if (arg === '--help' || arg === '-h') {
      usage();
      process.exit(0);
    }
  }
  return opts;
}

function main() {
  const opts = parseArgs(process.argv.slice(2));

  if (opts.init) {
    const dir = opts.initDir || process.cwd();
    const target = path.join(dir, 'team.json');
    const source = path.join(ROOT, 'examples', 'team.example.json');
    if (fs.existsSync(target)) {
      console.error(`refusing to overwrite existing ${target}`);
      return 1;
    }
    // The destination directory may not exist yet - copyFileSync does not create it.
    fs.mkdirSync(dir, { recursive: true });
    fs.copyFileSync(source, target);
    console.log(`wrote starter blueprint -> ${target}`);
    console.log('edit it, then run: mcode-team-builder --blueprint team.json');
    return 0;
  }

  if (!opts.blueprint) {
    usage();
    return 1;
  }
  if (!fs.existsSync(opts.blueprint)) {
    console.error(`blueprint not found: ${opts.blueprint}`);
    return 1;
  }

  const py = pythonCommand();
  if (!py) {
    console.error('Python 3.9+ is required but was not found on PATH.');
    return 1;
  }

  const scaffold = [
    path.join(SCRIPTS, 'scaffold_team.py'),
    '--blueprint', opts.blueprint,
  ];
  if (opts.dataDir) scaffold.push('--data-dir', opts.dataDir);
  if (opts.dryRun) scaffold.push('--dry-run');

  let code = runPython(py, scaffold);
  if (code !== 0) return code;
  if (opts.dryRun) return 0;

  const validate = [
    path.join(SCRIPTS, 'validate_team.py'),
    '--blueprint', opts.blueprint,
  ];
  if (opts.dataDir) validate.push('--data-dir', opts.dataDir);
  code = runPython(py, validate);
  if (code === 0) {
    console.log('\nNext: register each agent with `mavis agent create`, then build the');
    console.log('orchestrator roster with scripts/build_roster_skill.py — or just say the');
    console.log('request in MiniMax Code and let the skill do the whole flow.');
  }
  return code;
}

process.exit(main());
