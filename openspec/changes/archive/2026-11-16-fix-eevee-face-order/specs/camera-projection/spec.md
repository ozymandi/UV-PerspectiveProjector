# Spec Delta

## ADDED Requirements

### Requirement: Correct face order in EEVEE
Projected objects SHALL render in EEVEE with their faces in correct depth order, so that no face of an object shows through a nearer face of the same object, while keeping transparency outside camera A's frame.

#### Scenario: Box seen from behind
- **GIVEN** a projected box
- **WHEN** it is rendered in EEVEE from a camera behind it
- **THEN** the image shows only the faces nearest to that camera, matching a Cycles render of the same view

#### Scenario: Material from an earlier version
- **GIVEN** a .blend file whose projection material was created by version 1.2.0 or earlier
- **WHEN** the user projects onto an object again
- **THEN** the object gets a projection material that renders with correct face order
