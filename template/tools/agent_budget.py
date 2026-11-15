"""Claude Code hooks for model routing and subagent step budgets (owner: docs/model-routing.md).

  python tools/agent_budget.py pre    PreToolUse, every tool
  python tools/agent_budget.py post   PostToolUse, every tool

Main session: an Agent call must name a tier agent, keep its model, and start the brief with a Tier line.
Subagent (payload has agent_id): count tool calls against .claude/agent-budgets.json, stop on stuck
signals (identical call repeated, one file edited too often), warn near the budget, refuse nested
delegation. Exit 2 blocks the call (pre) or shows the message to the agent (post).
"""
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / '.claude' / 'agent-budgets.json'
DISPATCH_TOOLS = {'Agent', 'Task'}
WRITE_TOOLS = {'Edit', 'Write', 'MultiEdit', 'NotebookEdit'}
READ_TOOLS = {'Read', 'Grep', 'Glob', 'LS', 'WebFetch', 'WebSearch'}
TIER_LINE = re.compile(r'^\s*Tier:\s*([\w.-]+)\s+[-–—]\s+rule\s+\d+\s*:\s*\S', re.I | re.M)
REPORT = 'Stop now and end with the report format from your instructions.'

def load_config(path=CONFIG):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def state_path(session, agent):
    base = Path(os.environ.get('AGENT_BUDGET_STATE') or Path(tempfile.gettempdir(), 'claude-agent-budget'))
    safe = lambda value: re.sub(r'[^\w.-]', '_', str(value))[:80] or 'unknown'
    return base / safe(session) / f'{safe(agent)}.json'

def load_state(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {'calls': 0, 'seen': {}, 'edits': {}, 'read_streak': 0, 'warned': [], 'stopped': ''}

def save_state(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(state), encoding='utf-8')
    os.replace(temporary, path)

def dispatch_errors(tool_input, config):
    """Checks on an Agent call from the main session.

    Agents with a "models" list are built-in: their definition pins no model (they may inherit the
    session model), so the call must name one from the list. Project tier agents pin their model in
    .claude/agents/, so the call must not override it. Unlisted agent types are refused.
    """
    agent = tool_input.get('subagent_type') or ''
    entry = config['agents'].get(agent)
    if entry is None:
        return [f'subagent_type {agent or "(none)"!r} is not allowed; use one of {", ".join(config["agents"])}.']
    errors, model = [], tool_input.get('model') or ''
    if 'models' in entry and model not in entry['models']:
        errors.append(f'built-in agent {agent} needs model set to one of {", ".join(entry["models"])}.')
    elif 'models' not in entry and model:
        errors.append(f'{agent} pins its model in .claude/agents/; do not override it.')
    head = '\n'.join((tool_input.get('prompt') or '').strip().splitlines()[:3])
    match = TIER_LINE.search(head)
    if not match:
        errors.append('the brief must start with "Tier: <agent> - rule <n>: <reason>".')
    elif match[1] != agent:
        errors.append(f'the Tier line names {match[1]} but subagent_type is {agent}.')
    return errors

def budget_of(agent, config):
    return config['agents'].get(agent, {}).get('tool_calls', config.get('default_tool_calls', 30))

def pre_step(state, agent, tool_name, tool_input, config):
    """Count one subagent tool call. Return a blocking message, or None to allow it."""
    if state.get('stopped'):
        return state['stopped']
    if tool_name in DISPATCH_TOOLS:
        return 'subagents do not delegate; report back and let the session model dispatch.'
    state['calls'] += 1
    key = hashlib.sha256(f'{tool_name}\0{json.dumps(tool_input, sort_keys=True)}'.encode('utf-8')).hexdigest()
    state['seen'][key] = state['seen'].get(key, 0) + 1
    path = (tool_input.get('file_path') or tool_input.get('notebook_path')) if tool_name in WRITE_TOOLS else None
    if path:
        state['edits'][path] = state['edits'].get(path, 0) + 1
        state['read_streak'] = 0
    elif tool_name in READ_TOOLS:
        state['read_streak'] += 1
    budget = budget_of(agent, config)
    if state['calls'] > budget:
        state['stopped'] = f'step budget exhausted ({budget} tool calls). {REPORT}'
    elif state['seen'][key] >= config.get('repeat_limit', 3):
        state['stopped'] = f'identical {tool_name} call made {state["seen"][key]} times; you are looping. {REPORT}'
    elif path and state['edits'][path] >= config.get('same_file_edits', 6):
        state['stopped'] = f'{path} edited {state["edits"][path]} times; you are going in circles. {REPORT}'
    return state['stopped'] or None

def post_step(state, agent, config):
    """Return one-time warnings to show the subagent after a call, or an empty list."""
    messages, budget = [], budget_of(agent, config)
    if state['calls'] >= config.get('warn_at', 0.8) * budget and 'budget' not in state['warned']:
        state['warned'].append('budget')
        messages.append(f'{state["calls"]}/{budget} tool calls used. Wrap up: finish the current step, then report.')
    read_only = config['agents'].get(agent, {}).get('read_only', False)
    if (not read_only and state['read_streak'] >= config.get('read_streak', 15)
            and 'streak' not in state['warned']):
        state['warned'].append('streak')
        messages.append(f'{state["read_streak"]} read-only calls in a row without an edit. '
                        'Act on what you know, or report what blocks you.')
    return messages

def handle(mode, payload, config):
    """Return (exit_code, message) for one hook payload."""
    tool_name = payload.get('tool_name') or ''
    tool_input = payload.get('tool_input') or {}
    agent_id = payload.get('agent_id')
    if not agent_id:
        if mode == 'pre' and tool_name in DISPATCH_TOOLS:
            errors = dispatch_errors(tool_input, config)
            if errors:
                return 2, 'Blocked by tools/agent_budget.py: ' + ' '.join(errors) + ' See docs/model-routing.md.'
        return 0, ''
    agent = payload.get('agent_type') or 'unknown'
    path = state_path(payload.get('session_id') or 'session', agent_id)
    state = load_state(path)
    if mode == 'pre':
        message = pre_step(state, agent, tool_name, tool_input, config)
        save_state(path, state)
        return (2, f'Blocked by tools/agent_budget.py: {message}') if message else (0, '')
    messages = post_step(state, agent, config)
    save_state(path, state)
    return (2, 'agent_budget: ' + ' '.join(messages)) if messages else (0, '')

def main(argv):
    mode = argv[1] if len(argv) > 1 else ''
    if mode not in ('pre', 'post'):
        print('usage: agent_budget.py pre|post', file=sys.stderr)
        return 1
    try:
        payload = json.load(sys.stdin)
        config = load_config()
    except (OSError, ValueError) as error:
        print(f'agent_budget: skipped ({error})', file=sys.stderr)
        return 0
    code, message = handle(mode, payload, config)
    if message:
        print(message, file=sys.stderr)
    return code

if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
