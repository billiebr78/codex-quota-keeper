# Start here / Comece aqui

## Português

O Codex Quota Keeper é um conjunto de ferramentas para sessões eficientes do Codex no VS Code e no terminal. Ele **não desbloqueia cotas** e não é um medidor do limite da assinatura.

1. Instale Python 3.11+ e o Codex no VS Code.
2. Clone este repositório e execute `python -m pip install -e .`.
3. Execute `cqk doctor` para conferir o ambiente (somente leitura).
4. Em **outro projeto**, execute `cqk install --project "CAMINHO_DO_PROJETO"` para visualizar as alterações.
5. Se aprovar, repita com `--apply`.
6. Abra uma **nova** conversa do Codex no VS Code para usar as instruções e os hooks instalados.
7. Preencha o `HANDOFF.md` do projeto quando houver uma etapa longa. Não cole históricos inteiros no novo chat.

Para desfazer, use `cqk uninstall --project "CAMINHO_DO_PROJETO" --apply`. O handoff e os backups ficam preservados.

**Permissões:** somente instale hooks em projetos em que confia. Em algumas versões do Codex a execução exige que você autorize o hook.

## English

Install Python 3.11+; clone this repository; run `python -m pip install -e .`.
Run `cqk doctor`, then preview `cqk install --project /path/to/project`.
Use `--apply` only after inspecting the changes. Start a fresh Codex conversation afterwards.
The project `HANDOFF.md` is for verified milestones and a precise next step; do not treat it as a replacement for tests.

See the [README](README.md), [configuration](docs/CONFIGURATION.md), and [architecture](docs/ARCHITECTURE.md).
