# Processing Rules

These rules are the executable interpretation of the inspection specification. Implement them as tested functions, not as prompts.

## Points List

1. Detect the point and text columns using header aliases and sampled values.
2. Ignore blank columns between source columns without depending on their letters.
3. Identify a valid point address from values such as `Point 2`, `P2`, or `PT 2`, allowing spaces.
4. Normalize the address to an integer from 1 through 255.
5. Reject rows containing `unassigned`, placeholder point text, a dash-only text value, or an address outside 1 through 255.
6. When text is wrapped across following rows, append continuation text to the preceding valid point until the next point or structural boundary.
7. Keep only the normalized point address and point text for the point-processing output.
8. Preserve raw values and a decision reason in the audit record.

## Initiating Devices

- Create one device row for each accepted point.
- Map point text to Device Type using explicit configurable rules.
- Apply deterministic location rules where the description is known, such as RX Motion to Pharmacy.
- Leave location blank and create a review item when no rule applies.
- Never infer a location silently.

## Event History

1. Detect time, point address, description, and event-type fields by header aliases and content.
2. Retain only event types `A` and `T` in the first release.
3. Normalize point addresses using the same function used for Points List records.
4. Parse timestamps with an explicit timezone configured for the inspection.
5. Select the earliest qualifying timestamp for each point.
6. Preserve all candidate events in the audit trail.
7. Flag malformed timestamps, missing addresses, duplicate point definitions, and points without a qualifying event.

## Open decisions to confirm with sample files

- Exact customer output template and whether Excel, PDF, or both are required.
- Whether event type meanings vary by customer.
- Tie-breaking when two qualifying events have the same timestamp.
- Whether PDF input is text-based or scanned and therefore requires OCR.
- Complete list of device-type and location rules.

