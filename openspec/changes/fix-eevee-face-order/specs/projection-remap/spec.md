# Spec Delta

## ADDED Requirements

### Requirement: Correct face order in EEVEE after Remap
Remapped objects SHALL render in EEVEE with their faces in correct depth order, so that no face of an object shows through a nearer face of the same object, while keeping transparency where the projection was outside camera A's frame.

#### Scenario: Remapped box seen from behind
- **GIVEN** a remapped box whose back faces show the Hidden colour
- **WHEN** it is rendered in EEVEE from a camera behind it
- **THEN** the back faces show the flat Hidden colour, as in Cycles, with no photo from the front faces mixed in
