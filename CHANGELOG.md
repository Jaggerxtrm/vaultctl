
## [Unreleased]

### Project maintenance

- **Update specialists workflow guide** ([8a6652a](https://github.com/Jaggerxtrm/vaultctl/commit/8a6652aa9765ad83f6eb51204856e03f50eb7d67)) — 2026-05-19 09:35


- **Pull iron-review-hardening updates (v3.17.0-pre soak)** ([c0c7fb2](https://github.com/Jaggerxtrm/vaultctl/commit/c0c7fb255e709bbd23651753f4854a00f36c8279)) — 2026-05-25 00:35

  Mirrored from ~/dev/specialists ahead of v3.17.0 minor release for the
  soak period:

  - .specialists/default/{reviewer,code-sanity,executor,debugger}.specialist.json
    → Iron-style behavior: SCRUTINY tiers, auto-escalation, ddiff re-review,
      obligations discipline (executor/debugger), seconder-gate (code-sanity)
  - .specialists/default/obligations-scanner.specialist.json (NEW)
    → READ_ONLY pre-review marker scan (TODO/FIXME/HACK/XXX/TEMP/WIP/NOTE)
  - .xtrm/skills/default/using-specialists-v3/SKILL.md (v3.4 → v3.5)
    → SCRUTINY taxonomy, Git State Precondition, Cherry-Pick Playbook
      canonical, sp merge / sp epic merge prohibited (rule #9 inverted)


- **Sync xtrm v0.9.0 assets** ([6233bc0](https://github.com/Jaggerxtrm/vaultctl/commit/6233bc032740bfe76157232a28658c1bd4d300d9)) — 2026-06-07 01:47


- **Remove obsolete runtime artifacts** ([74933bf](https://github.com/Jaggerxtrm/vaultctl/commit/74933bfd9be65d8df08bdc6743c5cedc04e6d80d)) — 2026-06-07 01:48


- **Apply bd auto-stage patch (xtrm-tools auto-applied)** ([15647f1](https://github.com/Jaggerxtrm/vaultctl/commit/15647f1258a560773803ced6379a06314cdee4de)) — 2026-07-13 06:01


- **Add git-cliff config and changelog** ([082f388](https://github.com/Jaggerxtrm/vaultctl/commit/082f3887629c4fe339f507bee90cc2446ecdf4ca)) — 2026-07-14 00:56

  Generic type-based parsers; repo-specific scopes to be tuned (see P0 bead).


# Changelog

All notable changes to this project are documented here.

