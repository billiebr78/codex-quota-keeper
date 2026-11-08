# Codex Quota Keeper

**Practical context and token-efficiency tools for Codex in VS Code and the Codex CLI.**

[Português](#início-rápido) · [English](#quick-start-english)

> **Status:** v0.1 — functional, conservative prototype. No measured savings claim; no quota bypass.

Codex Quota Keeper helps keep coding sessions focused and auditable. It offers small `AGENTS.md` rules, optional native Codex hooks, JSONL token reports, a handoff template, and an explicitly invoked session relay. It **does not** increase OpenAI usage limits, read account billing, or guarantee lower token consumption.

## Design principles

- **Native first:** use Codex's existing `AGENTS.md`, `.codex/hooks.json`, and `codex exec` interfaces.
- **Safe by default:** installer previews changes; apply is explicit; existing files are backed up and preserved.
- **Minimal dependency surface:** Python 3.11+ standard library; no API keys or browser automation.
- **No false accounting:** JSONL reports measure tokens returned by Codex, *not* subscription percentage or money saved.
- **Local control:** no prompt collection, analytics endpoint, or hidden autonomous operation.

## Features

| Capability | Status | Notes |
| --- | --- | --- |
| User/project policy in `AGENTS.md` | Available | Managed, idempotent block |
| Prompt/tool-count warnings | Available | Codex `UserPromptSubmit` and `PostToolUse` hooks; *counts*, not tokens |
| Model-request event counters | Experimental | `PostModelRequest` records attempts, outcomes and optional token fields when emitted by Codex; VS Code validation pending |
| Token reports from `codex exec --json` | Available | Input, cached input, output, reasoning output where present |
| Comparative token report | Available | `cqk compare` compares equivalent verified runs |
| Optional native Codex Skill | Available | `.agents/skills/codex-quota-keeper/SKILL.md` — manual installation |
| Project handoff template | Available | Preserves verified state and exact next step |
| Optional fresh-session relay | Available | CLI-only, explicit invocation, bounded rounds |
| Subagent/config tuning | Documented | Suggestion only; never silently modifies `config.toml` |
| Automatic VS Code session replacement | Not implemented | Requires a supported session lifecycle integration |
| Subscription quota percentage | Not implemented | No reliable public account quota mapping |
| Automatic savings benchmark | Planned | Compare equivalent verified tasks |

## Início rápido

Requisitos: Python **3.11+**; Codex instalado no VS Code ou no terminal. Abra um terminal no diretório do projeto:

```powershell
git clone https://github.com/billiebr78/codex-quota-keeper.git
cd codex-quota-keeper
py -m pip install -e .
py -m codex_quota_keeper doctor
```

Prévia do instalador para um projeto existente (nenhum arquivo é alterado):

```powershell
cqk install --project "C:\caminho\do\seu-projeto"
```

Aplicar ao projeto escolhido:

```powershell
cqk install --project "C:\caminho\do\seu-projeto" --apply
```

Isso adiciona uma seção delimitada em `AGENTS.md`, instala hooks `UserPromptSubmit`, `PostToolUse` e `PostModelRequest` em `.codex/hooks.json` e cria `HANDOFF.md` **apenas se não existir**. Os hooks exigem que o projeto seja confiável no Codex; pode haver confirmação para confiar neles. Reinicie a sessão do Codex depois da instalação.

Outros comandos:

```powershell
cqk doctor --project "C:\caminho\do\seu-projeto"
cqk report "C:\logs\exec.jsonl"
cqk handoff --project "C:\caminho\do\seu-projeto"
cqk uninstall --project "C:\caminho\do\seu-projeto" --apply
```

Para gerar dados de uso, rode explicitamente um comando do Codex CLI:

```powershell
codex exec --json "Descreva a estrutura deste projeto" > exec.jsonl
cqk report exec.jsonl
# Execute a comparable second task and compare both results:
cqk compare baseline.jsonl optimized.jsonl
```

**Atenção:** o arquivo JSONL pode conter texto, comandos e resultados sensíveis da sessão. Não o publique; ele não é necessário para os hooks.

### Relay opcional (CLI, não a sessão do VS Code)

```powershell
cqk relay --project "C:\caminho\do\seu-projeto" --rounds 2 --sandbox workspace-write
```

O relay cria **novas** execuções `codex exec`, cada uma lendo `HANDOFF.md`. Não retoma uma sessão existente. Use somente depois de revisar o próximo passo no handoff; ele pode alterar arquivos no projeto. Por padrão, a caixa de areia é **read-only**; `workspace-write` deve ser selecionado explicitamente. Não há execução recorrente ou em segundo plano.

### Windows com a extensão do Codex (sem CLI separado)

Se `python --version` apontar para a Microsoft Store, mas `py --version` encontrar Python 3.11+, não reinstale o Python: use `py -m ...`. O Codex Quota Keeper funciona com a extensão `openai.chatgpt` instalada no VS Code; o CLI separado é opcional para instalação, diagnóstico e hooks (necessário apenas para comandos que executam `codex exec`).

Use uma pasta de teste antes de aplicar qualquer coisa aos seus projetos:

```powershell
cd D:\Homebrew
git clone https://github.com/billiebr78/codex-quota-keeper.git
cd codex-quota-keeper
py -m pip install -e .
py -m codex_quota_keeper doctor
New-Item -ItemType Directory -Force D:\Homebrew\cqk-test | Out-Null
py -m codex_quota_keeper install --project D:\Homebrew\cqk-test
# Após conferir a prévia:
py -m codex_quota_keeper install --project D:\Homebrew\cqk-test --apply
```

Usar `py -m codex_quota_keeper` evita depender do comando `cqk` no PATH. A ausência de `codex` no PATH não é tratada como ausência da extensão do VS Code.
## Quick start (English)

```sh
git clone https://github.com/billiebr78/codex-quota-keeper.git
cd codex-quota-keeper
python -m pip install -e .
cqk doctor
cqk install --project /path/to/your-project          # dry run
cqk install --project /path/to/your-project --apply  # apply, with backups
cqk report /path/to/codex-exec.jsonl
```

To enable the optional Codex Skill in another repository, copy the folder `.agents/skills/codex-quota-keeper` from this repository to `<your-project>/.agents/skills/codex-quota-keeper`. Codex discovers the skill when relevant or when you explicitly request `$codex-quota-keeper`. The installer does not install this optional Skill automatically.

Use `cqk --help` for all commands. For advanced settings, see [Configuration](docs/CONFIGURATION.md) and [Architecture](docs/ARCHITECTURE.md).

## Safety and uninstall

- Installer does not touch authentication, API keys, approvals, sandbox policy, or `config.toml`.
- Installation is scoped to a selected project unless you deliberately use `--scope user`.
- Existing `AGENTS.md` and hook definitions are **merged**, not replaced. Before changing an existing file, the installer saves a timestamped backup.
- Uninstall removes only the managed policy block and identifiable managed hook commands. It leaves user files, handoff data and backups intact.
- The `cqk hook` command stores only counters and warning milestones keyed by a hash of the session ID. It does not store user prompts or tool arguments.
- Be conservative with unattended `codex exec` runs. Native hook guards are *advisory*, not a security sandbox.

## Development

```sh
python -m pip install -e .
python -m unittest discover -s tests -v
python -m compileall -q src
```

The test suite runs offline on Linux and Windows. See [ROADMAP](docs/ROADMAP.md) for features not yet implemented.

## Attribution

Inspired by [JN's Quota Keeper](https://github.com/JNSoftworks/jns-quota-keeper) by Jaber Felippe Neto (JN Softworks). This is an independent Codex implementation, not an official port or an affiliated project. No JN's Quota Keeper source code or guide text is incorporated in this repository. Original project licenses: CC BY 4.0 for its guide and MIT for its scripts.

Codex, ChatGPT and OpenAI are trademarks of OpenAI; this project is not affiliated with or endorsed by OpenAI.

## License

MIT — see [LICENSE](LICENSE).
