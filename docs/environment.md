# Environment variables

ObsidianKi reads optional settings from `~/.config/obsidianki/.env` (the same file the interactive setup writes for API keys). On Windows, that is under your user profile, e.g. `C:\Users\<you>\.config\obsidianki\.env`.

## Obsidian connection

| Variable | Values | Description |
|----------|--------|-------------|
| `OBSIDIAN_CLIENT` | `auto`, `rest`, `cli` | How the app talks to your vault. Default **`auto`**: uses the Local REST API when `OBSIDIAN_API_KEY` is set; otherwise tries Obsidian CLI (1.12+) if `obsidian` is on your `PATH` and responds to `obsidian version`. |
| `OBSIDIAN_VAULT` | Vault name or id | **CLI only.** Passed as `vault=…` so the CLI targets a specific vault instead of the active or cwd vault. |
| `OBSIDIAN_CLI_PATH` | Path to executable | Use when the `obsidian` command is not on your `PATH`. |
| `OBSIDIAN_CLI_TIMEOUT` | Seconds (integer) | Subprocess timeout for CLI calls. Default is `30`. |

REST mode still expects `OBSIDIAN_API_KEY` from the Local REST API plugin, as configured during setup.
