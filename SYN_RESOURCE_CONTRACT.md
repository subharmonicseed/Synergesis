# AEGIS resource matching contract

Capability grants carry a `resource_match_mode`. The mode is part of the signed
payload for the opt-in `exact` and `path` contracts, and therefore cannot be
changed without invalidating the grant. Deserialization rejects unknown modes.

`legacy_prefix` is the default for compatibility with grants issued before this
field existed. Its original lexical `resource.startswith(scope)` behavior is
preserved, including the historical wildcard `*`; deployments should treat
legacy prefixes as literal lexical prefixes rather than path scopes.

New grants can select:

- `exact`: the requested resource must equal a listed scope.
- `path`: the requested resource must equal a listed scope or be below it at a
  `/` component boundary. `.` and `..` components, backslashes, and NUL are
  rejected to avoid traversal and platform separator ambiguity. A scope of `*`
  remains an explicit all-resource grant.

The mode itself is signed for these new contracts. The default legacy mode is
omitted from its signed representation, preserving verification of previously
issued grant signatures and identifiers. `resource_prefixes` remains the
serialized field name so old storage readers and integrations retain a clear
migration path.
