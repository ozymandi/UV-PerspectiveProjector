# Spec Delta

## Purpose

Build simple geometry that lines up with the calibrated photo (floor, walls, boxes, ceilings) by clicking on the photo in camera A's view, and check its alignment, so the photo can be projected onto separate scene elements without manual modelling.

## ADDED Requirements

### Requirement: Blockout tools need a calibrated camera
The Blockout tools SHALL be available only when camera A and its photo exist, SHALL switch the 3D view to look through camera A when started, and SHALL be cancellable with Esc or right click without changing the scene.

#### Scenario: Not calibrated
- **WHEN** the user opens the panel before calibrating
- **THEN** the Blockout tools are disabled with a hint to run Calibrate first

#### Scenario: Cancel a tool
- **WHEN** the user starts the Box tool, clicks one corner and presses Esc
- **THEN** no object is created and the scene is unchanged

### Requirement: Clicks land on existing surfaces before the ground
A click SHALL be placed on the nearest blockout surface hit by the ray from camera A through the clicked pixel, and on the ground plane when no blockout surface is hit; a click that hits neither SHALL be ignored with a message.

#### Scenario: Box standing on a table
- **GIVEN** a blockout box whose top is 0.75 m high
- **WHEN** the user draws a Box footprint by clicking on that top
- **THEN** the new box's base is at 0.75 m

#### Scenario: Click above the horizon
- **WHEN** the user clicks the sky with no blockout surface behind it
- **THEN** the click is ignored and the status bar says it did not hit the ground or a surface

### Requirement: Floor from clicked corners
The Floor tool SHALL create a ground polygon whose corners lie where the user clicked, finished with Enter or a click on the first corner.

#### Scenario: Floor area
- **WHEN** the user clicks four floor corners in the photo and presses Enter
- **THEN** a four-sided ground polygon exists whose corners project onto the clicked pixels through camera A within 1 px

### Requirement: Wall from its base and top
The Wall tool SHALL create a vertical rectangle from two base points and a top click, with the top height taken from the point vertically above the base under the cursor; the base direction SHALL snap to the world X or Y axis when within 5 degrees of it.

#### Scenario: Wall along an axis
- **WHEN** the user clicks two points along the bottom of a wall that runs along X and then a point on its top edge
- **THEN** a vertical wall exists along X whose bottom and top edges project onto the clicked line and top point within 2 px

#### Scenario: Oblique wall
- **WHEN** the wall base is 30 degrees from both axes
- **THEN** the wall keeps that direction instead of snapping

### Requirement: Box from footprint and height
The Box tool SHALL create an axis-aligned box from two opposite footprint corners and a height click, standing on the surface the footprint was clicked on.

#### Scenario: Bench
- **WHEN** the user clicks two opposite floor corners of a bench and then its top edge
- **THEN** a box exists whose footprint corners and top edge project onto the clicked pixels within 2 px through camera A

### Requirement: Ceiling at a clicked height
The Ceiling tool SHALL create a horizontal plane at the height of a point clicked on an existing vertical blockout surface, covering the horizontal extent of the existing blockout.

#### Scenario: Ceiling from a wall
- **GIVEN** a blockout wall
- **WHEN** the user clicks the line where the ceiling meets that wall
- **THEN** a horizontal plane exists at that height spanning the blockout's extent

#### Scenario: Ceiling without a wall
- **WHEN** the user clicks a point that is not on a vertical blockout surface
- **THEN** no plane is created and the status bar asks for a click on a wall

### Requirement: Blockout objects are ready for projection
Objects created by the Blockout tools SHALL be meshes in a `Blockout` collection, named after their tool with a running number, with flat faces and no modifiers, so the existing Project and Remap work on them unchanged.

#### Scenario: Project the blockout
- **WHEN** the user selects all objects in the Blockout collection and presses Project, then Remap
- **THEN** each object gets its own projection and baked texture, and the render through camera A matches the photo

### Requirement: Single undo step per tool
Each completed Blockout tool use SHALL be undoable in one undo step.

#### Scenario: Undo a box
- **WHEN** the user creates a box and presses Ctrl+Z once
- **THEN** the box is gone and nothing else changed

### Requirement: Alignment overlay
The add-on SHALL provide a toggle that draws the edges of blockout and projected objects over the photo while looking through camera A, in a colour readable over the photo, updating live when objects move.

#### Scenario: Misplaced box is visible
- **WHEN** the overlay is on and the user moves a blockout box 10 cm sideways
- **THEN** its drawn edges move off the matching edges in the photo while the photo stays put

#### Scenario: Overlay off outside camera A
- **WHEN** the view does not look through camera A
- **THEN** the overlay draws nothing
