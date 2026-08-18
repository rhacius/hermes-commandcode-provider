# plugins/

## Responsibility

`plugins/` is the source-tree boundary for Hermes plugin packages. It currently
contains the `model-providers/` category and, beneath that category, the
`commandcode/` provider package. This directory is an aggregate/container, not
the implementation of the Command Code bridge and not a second provider
registration layer.

Its job is to keep Hermes-facing extension artifacts in the layout expected by
plugin discovery: category directories contain concrete plugin directories,
and each concrete plugin supplies its metadata and provider profile. The
bridge, model catalog, launchers, and configuration helpers live outside this
tree and are deliberately not part of this aggregate's responsibility.

## Design patterns/abstractions

* **Hierarchical plugin namespace.** `model-providers/` is the extension
  category; `model-providers/commandcode/` is the concrete plugin. The
  aggregate level owns no executable module or shared abstraction.
* **Metadata plus registration profile.** The leaf's `plugin.yaml` declares the
  Hermes plugin identity (`kind: model-provider`, name, version, and
  description), while its `__init__.py` adapts the Command Code service to
  Hermes' `ProviderProfile` API and calls `register_provider`.
* **Declarative provider configuration.** The leaf profile captures aliases,
  authentication environment, local OpenAI-compatible base/models URLs,
  defaults, the omitted fixed temperature behavior, and fallback model IDs.
  The aggregate does not duplicate or merge those settings.
* **Separated transport boundary.** Provider discovery/configuration is kept
  separate from request transport: the profile points Hermes at the local
  bridge, while `commandcode_bridge.py` handles upstream authentication,
  translation, streaming, and catalog behavior.

The nested codemaps document different scopes: this file documents only the
`plugins/` container; `model-providers/codemap.md` documents the provider
category; and `model-providers/commandcode/codemap.md` documents the concrete
Command Code package and its profile details.

## Flow

1. Installation creates the corresponding directory under
   `$HERMES_HOME/plugins/model-providers/` and copies the leaf `__init__.py`
   and `plugin.yaml`; it does not install this source codemap as runtime code.
2. Hermes discovers the `model-provider` plugin from the installed hierarchy,
   loads the leaf module, and the module registers the `commandcode`
   `ProviderProfile` with Hermes' provider registry.
3. Hermes resolves the provider name or one of its aliases and uses the
   profile's `http://127.0.0.1:8788/v1` endpoints and model defaults. Requests
   then leave the plugin boundary and enter the local bridge.
4. The bridge forwards them to Command Code and returns the OpenAI-compatible
   response; the plugin directory itself does not handle request data or
   responses.

## Integration

* **Installer:** `install.sh` is the source-tree integration point. It copies
  only `plugins/model-providers/commandcode/{__init__.py,plugin.yaml}` into the
  Hermes installation, alongside `commandcode_bridge.py`, `models.json`, and
  the launchers.
* **Hermes plugin API:** the leaf module imports `ProviderProfile`,
  `OMIT_TEMPERATURE`, and `register_provider` from Hermes' `providers` package.
  The aggregate directory has no direct import or runtime hook.
* **Local bridge:** the registered profile targets the bridge's `/v1` API at
  the configured local host/port (defaults `127.0.0.1:8788`). The launcher
  starts or reuses that bridge before invoking Hermes; this is a runtime
  dependency of the leaf provider, not a child of `plugins/`.
* **Configuration and catalog:** `scripts/configure_hermes.py` can set the
  `commandcode` provider and model catalog in Hermes configuration, while
  `models.json` supplies the shared catalog used by installation/configuration
  and the bridge. These root-level integrations complement plugin discovery;
  they are not files owned by this directory.
