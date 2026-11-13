# Spec Delta

## Purpose

Freeze a live camera projection into a regular UV map and a baked image, so a projected object keeps its texture independently of the projection camera and can be moved, deformed or painted.

## ADDED Requirements

### Requirement: Remap projected objects
The add-on SHALL provide a Remap action that works on the selected objects that have a live projection from camera A, and SHALL skip and report selected objects without one.

#### Scenario: Remap a projected plane
- **WHEN** the user selects the projected plane and presses Remap
- **THEN** the plane gets a new baked image on a regular UV map and the panel reports success

#### Scenario: Object without projection
- **WHEN** the selection contains an object that was never projected
- **THEN** that object is left unchanged and the panel reports it was skipped

### Requirement: Regular UV map for the bake
Remap SHALL bake into a regular UV map separate from the projection UV map: it SHALL reuse an existing non-projection UV map when the object has one, and SHALL create a non-overlapping unwrap otherwise.

#### Scenario: Object without its own UVs
- **GIVEN** the default projected plane, which has only the projection UV map
- **WHEN** the user presses Remap
- **THEN** a new non-overlapping UV map is created and used for the bake

#### Scenario: Object with existing UVs
- **GIVEN** a projected mesh that already had its own UV map before projection
- **WHEN** the user presses Remap
- **THEN** the bake goes into that existing UV map and no new unwrap is made

### Requirement: Baked image matches the projection
The baked image SHALL reproduce what the live projection showed, at a resolution derived from how many photo pixels the object covers in camera A (rounded to a power of two between 1024 and 8192, user-overridable), with transparency kept where the projection was outside camera A's frame.

#### Scenario: Same result through camera A
- **WHEN** the scene is rendered through camera A before and after Remap
- **THEN** the two renders match apart from resampling differences

#### Scenario: Resolution override
- **WHEN** the user sets the remap resolution to 2048 before pressing Remap
- **THEN** the baked image is 2048 pixels on its longer side

### Requirement: Object no longer depends on camera A
After Remap, the object's material SHALL use the baked image on the regular UV map, the projection modifier SHALL be removed, and the subdivision SHALL be kept.

#### Scenario: Move the object after Remap
- **WHEN** the user moves or rotates the remapped plane
- **THEN** the texture moves with the plane instead of sliding across it

#### Scenario: Camera A deleted
- **WHEN** the user deletes camera A after Remap
- **THEN** the remapped object still renders its texture unchanged through camera B

### Requirement: Baked image is saved
The baked image SHALL be saved as a file in a textures folder next to the .blend file when the file has been saved, and SHALL be packed into the .blend otherwise, so it is not lost on reload.

#### Scenario: Saved .blend
- **GIVEN** the .blend file has been saved to disk
- **WHEN** Remap finishes
- **THEN** a PNG with the object's name exists in the textures folder next to the .blend and the material references it

#### Scenario: Unsaved .blend
- **GIVEN** the .blend file was never saved
- **WHEN** Remap finishes and the user then saves the file
- **THEN** the baked image is stored inside the .blend

### Requirement: Remap leaves render settings unchanged
Remap SHALL restore the scene's render engine and bake settings to their previous values after baking.

#### Scenario: EEVEE scene
- **GIVEN** the scene uses EEVEE
- **WHEN** Remap finishes
- **THEN** the scene still uses EEVEE with the same settings as before

### Requirement: Single undo step for Remap
Remap SHALL be undoable in one undo step that restores the live projection.

#### Scenario: Undo Remap
- **WHEN** the user presses Remap and then Ctrl+Z once
- **THEN** the object again has the projection modifier and the projection material
