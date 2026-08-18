# plugins/model-providers/

## Responsibility

This directory contains Hermes model-provider plugin packages. The active
`commandcode/` package describes Command Code as a native Hermes provider: its
identity, aliases, authentication environment variable, local OpenAI-compatible
endpoints, defaults, and fallback model catalog. It is configuration and
registration glue, not the API transport itself; the transport is implemented
by the repository-level `commandcode_bridge.py`.

## Design patterns / abstractions

- **Declarative provider profile:** `commandcode/__init__.py` creates one
  `ProviderProfile` rather than implementing provider-specific request logic.
  Hermes owns the common provider behavior and consumes the profile fields.
- **Import-time registration:** the module calls `register_provider(commandcode)`
  as its final operation, so Hermes discovery registers the profile as a side
  effect of importing the plugin.
- **Adapter boundary:** the profile exposes the bridge using the provider API
  abstraction (`base_url` and `models_url` both point at
  `http://127.0.0.1:8788/v1`). The bridge adapts Hermes/OpenAI chat-completion
  traffic to Command Code's upstream API outside this directory.
- **Fallback/default policy:** `default_max_tokens` is `32000`, the auxiliary
  model is `deepseek/deepseek-v4-flash`, and `fallback_models` enumerates the
  supported model IDs for discovery or offline operation. `fixed_temperature`
  is `OMIT_TEMPERATURE`, allowing the bridge/upstream to control sampling rather
  than forcing a provider-level fixed value.
- **Plugin metadata:** `commandcode/plugin.yaml` identifies the package as a
  `model-provider`, version `0.2.0`, and records its human-facing description
  and author. Runtime behavior remains in the `ProviderProfile` declaration.

## Flow

1. Hermes scans the model-provider plugin directory and reads the nested
   `plugin.yaml` metadata, then imports `commandcode/__init__.py`.
2. Importing the module constructs the `commandcode` profile and registers it
   under `commandcode`; `command-code`, `commandcode-alpha`, and `cc` resolve
   through its aliases.
3. Hermes resolves credentials through the profile's
   `COMMANDCODE_API_KEY` declaration and sends model requests to the local
   bridge at `http://127.0.0.1:8788/v1`. The profile's model URL provides the
   corresponding `/models` discovery endpoint, while `fallback_models` remains
   available when discovery is unavailable.
4. The bridge, outside this directory, authenticates against Command Code,
   translates the OpenAI-compatible request, and returns the response to
   Hermes. The selected model and profile defaults determine the request
   parameters; the profile itself does not stream, translate, or call the
   upstream service.

## Integration

- **Hermes provider API:** depends on the host-provided `providers` package and
  specifically `providers.base.ProviderProfile` plus `OMIT_TEMPERATURE`; these
  are not defined in this repository.
- **Local bridge:** requires the bridge process to listen on loopback port
  `8788` and exposes the `/v1` base URL and `/v1/models` URL expected by Hermes.
  The launcher and systemd service start that process; the plugin does not.
- **Authentication:** advertises `COMMANDCODE_API_KEY` for Hermes configuration.
  The bridge additionally supports Command Code credential files, but that
  credential resolution is outside the plugin package.
- **Installation/configuration:** `install.sh` copies this directory's
  `__init__.py` and `plugin.yaml` into `~/.hermes/plugins/model-providers/commandcode/`.
  `scripts/configure_hermes.py` configures the matching `commandcode` provider
  and model catalog without patching Hermes.
- **Catalog relationship:** the profile's fallback IDs mirror the bundled
  repository `models.json` catalog and the bridge's live/fallback model output;
  changes to supported models should keep those sources aligned.
