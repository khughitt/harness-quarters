"""Origin evidence and evidence labels; consumers choose their own authorship policy."""

# Prefix spellings follow the existing readers and index adapters. Partial prefixes
# (paste, skills, permissions, shell and mode) intentionally keep their old matching.
_MARKERS = (
    ('system_reminder', '<system-reminder>'),
    ('task_notification', '<task-notification>'),
    ('pasted_content', '<pasted_content'),
    ('interrupt', '[Request interrupted by user'),
    ('command_name', '<command-name>'),
    ('bash_input', '<bash-input>'),
    ('local_command_stdout', '<local-command-stdout>'),
    ('local_command_stderr', '<local-command-stderr>'),
    ('bash_stdout', '<bash-stdout>'),
    ('bash_stderr', '<bash-stderr>'),
    ('agents_md', '# AGENTS.md'),
    ('environment_context', '<environment_context>'),
    ('instructions', '<INSTRUCTIONS>'),
    ('skills_instructions', '<skills_instruct'),
    ('turn_aborted', '<turn_aborted>'),
    ('permissions', '<permissions'),
    ('user_shell', '<user_shell'),
    ('collaboration_mode', '<collaboration_mode'),
)
_TYPED = frozenset({'command_name', 'bash_input', 'pasted_content'})
_INJECTED = frozenset(name for name, _prefix in _MARKERS) - _TYPED - {'interrupt'}
_BASES = {'origin': 'native', 'kind': 'native', 'structure': 'native',
          'agent_path': 'convention', 'local_command': 'convention', 'prefix_rule': 'heuristic'}


def origin(content, harness: str, native_kind=None, flags=()) -> dict:
    """Record both classifier texts: the first block as written and joined/stripped text."""
    if isinstance(content, str):
        lead, joined = content, content.strip()
    else:
        blocks = [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []
        if harness == 'codex':
            lead = next((b['text'] for b in blocks if isinstance(b.get('text'), str)), '')
            texts = [b['text'] for b in blocks if b.get('type') in ('input_text', 'output_text')
                     and isinstance(b.get('text'), str)]
        else:
            lead = next((b.get('text') for b in blocks if b.get('type') == 'text'), '')
            lead = lead if isinstance(lead, str) else ''
            texts = [b['text'] for b in blocks if b.get('type') == 'text' and isinstance(b.get('text'), str)]
        joined = '\n'.join(texts).strip()

    def position(text, prefix):
        at = text.find(prefix)
        return None if at < 0 else 'start' if at == 0 else 'inside'

    markers = [{'name': name, 'lead': position(lead, prefix), 'joined': position(joined, prefix)}
               for name, prefix in _MARKERS if prefix in lead or prefix in joined]
    return {'native_kind': native_kind if isinstance(native_kind, str) else None,
            'flags': sorted(set(flags) & {'meta', 'compaction_summary'}), 'markers': markers,
            'unrecognized_tag': {key: text.startswith('<') and not any(text.startswith(prefix)
                                  for _name, prefix in _MARKERS)
                                 for key, text in (('lead', lead), ('joined', joined))}}


def label(record: dict) -> None:
    """Add the rule/basis and resolve only the evidence that supports a label."""
    role, rule = record['role'], record['role_basis']
    basis = _BASES[rule]
    if rule == 'structure' and (role == 'dispatch' or 'interrupt_marker' in record['_flags']):
        basis = 'convention'
    if role == 'human' and rule == 'prefix_rule':
        role = 'user_channel_unattributed'
    evidence = record.get('origin')
    if rule == 'prefix_rule' and evidence is not None and any(evidence['unrecognized_tag'].values()):
        role = 'unknown'
    if evidence is not None and role in {'human', 'injected', 'dispatch', 'user_channel_unattributed'}:
        native = evidence['native_kind']
        starts = [m for m in evidence['markers'] if 'start' in (m['lead'], m['joined'])]
        conflict = [m for m in (starts if native == 'human' else evidence['markers'])
                    if m['name'] in (_INJECTED if native == 'human' else _TYPED)]
        if native is not None and conflict:
            role, rule, basis = 'unknown', 'conflict', 'heuristic'
            record['conflict'] = [{'native_kind': native}, {'markers': conflict}]
    record.update(role=role, rule=rule, role_basis=rule, basis=basis)
