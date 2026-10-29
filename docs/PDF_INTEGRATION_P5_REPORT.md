# P5 visual administration workspace

Administration now has a separate Integrations tab, with explicit refresh dispatch alongside the unchanged Users, Panel Types and Inspection Tasks tabs. Both integration cards expose version/status, included pages, fingerprint, coverage, upload, prior-version activation and enable/disable controls.

The packaged `api/integrations.js` asset provides page navigation and zoom, independent keyboard-accessible occurrence rectangles, two-way inventory selection/search, metadata/default/state/duplicate warnings, typed source selection, mapping dispositions, conditional rules, allowlisted transform configuration, font/overflow/missing policies, and a typed manual-input builder. Advanced input/group/condition definitions use editable, server-validated declarative JSON. Policies include panel applicability, signatures and supplemental declarations.

Unsaved edits survive polling, page changes and stale-save conflicts. Opening another version requires saving/discarding edits. Administrators can download local configuration before explicitly discarding/reloading. Diagnostic tests open as separately marked documents; each target must be explicitly verified against the current test before confirmed publication. Re-testing or changing a mapping resets local verification. Legacy PDF dialogs are independent.

Verification: real Chromium exercised duplicate-location selection, coordinate alignment at 50/100/200 percent zoom, keyboard selection, private edits during polling, an actual concurrent-save conflict and recovery, source mapping, tests, individual verification, confirmed publication, all existing admin tabs and a narrow viewport. The existing typed-checklist browser regression passed alongside it. Wheel contents include the new JavaScript and existing UI assets. Compile/whitespace checks passed.

No production deployment or template configuration occurred. Publication candidates still require business review and supplied-form visual acceptance in P8–P9. Production final previews/downloads remain P7. Resource-bounded preview rasterization uses the PDF crop box, matching inventory coordinates.
