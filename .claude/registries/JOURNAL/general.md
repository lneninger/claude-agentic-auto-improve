# Journal - general

> Project-tier lessons that fit no other domain file. This file is owned by the project: the plugin sync never writes it.
>
> Entry shape: a third-level heading made of the date, a dash and the title, then the fields Trigger, Source contract, Lesson, Apply when and Tags, each as a bold-label bullet. Trigger is one of: pre-approval critic, post-approval, post-impl divergence, manual. Entries are append-only: never reorder or rewrite one; add an indented Correction line instead. Titles are unique across the root file and every domain file of this registry.
>
> Add an entry with the registry append script, or by hand at the end of this file, above any leftovers section.

### 2026-11-16 — A new switch or setting file must be weighed against the Project profile before a new file is proposed
- **Trigger:** pre-approval critic
- **Source contract:** .claude/concepts/2026-11-16-file-based-switches.md
- **Lesson:** The first draft rejected per-hook rules files and settings.json as homes for the new switches but never mentioned the Project profile, which is already a committed per-project settings file and already carries the memory adapter's on/off setting. Before proposing a new settings file, name every existing settings file and say in writing why each does not fit. Here the profile holds project facts, forbids local-only slots, has no personal layer and is markdown that every hook would have to parse.
- **Apply when:** a contract proposes a new configuration, settings or switch file for a project.
- **Tags:** switch-file, project-profile, new-mechanism, reuse, settings

### 2026-11-16 — Moving a script's environment read into a shared helper changes its import list, so the vendored-file list and the way it reaches the helper must be stated
- **Trigger:** pre-approval critic
- **Source contract:** .claude/concepts/2026-11-16-file-based-switches.md
- **Lesson:** The first draft made `_contract_index.py` depend on a new helper in another folder, while an add-on manifest named `_contract_index.py` as a vendored helper but not the new one, and no block touched the manifest. When a change gives a vendored script a new dependency, the same contract must update the manifest list, or keep the script free of the dependency and let its callers pass the value in. The final design took the second route.
- **Apply when:** a contract adds an import or a settings read to a script that an add-on manifest vendors or copies.
- **Tags:** vendored-files, add-on-manifest, helper-dependency, import-list
