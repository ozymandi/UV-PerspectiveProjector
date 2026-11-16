# scene-blockout Specification

## Purpose

Build simple geometry that lines up with the calibrated photo (floor, walls, boxes, ceilings) by clicking on the photo in camera A's view, and check its alignment, so the photo can be projected onto separate scene elements without manual modelling.

## Requirements

### Requirement: Blockout tools need a calibrated camera
The Blockout tools SHALL be available only when camera A and its photo exist, SHALL switch the 3D view to look through camera A when started, and SHALL be cancellable with Esc or right click without changing the scene.

#### Scenario: Not calibrated
- **WHEN** the user opens the panel before calibrating
- **THEN** the Blockout tools are disabled with a hint to run Calibrate first

#### Scenario: Cancel a tool
- **WHEN** the user starts the Box tool, clicks one corner and presses Esc
- **THEN** no object is created and the scene is unchanged

### Requirement: Clicks land on existing surfaces before the ground
A click SHALL be placed on the nearest blockout surface hit by the ray from camera A through the clicked pixel, then on the ground plane, then on the selected reference plane when a reference corner is set; a click that hits none of them SHALL be ignored with a message.

#### Scenario: Box standing on a table
- **GIVEN** a blockout box whose top is 0.75 m high
- **WHEN** the user draws a Box footprint by clicking on that top
- **THEN** the new box's base is at 0.75 m

#### Scenario: Click above the horizon
- **WHEN** the user clicks the sky with no blockout surface behind it and no reference corner is set
- **THEN** the click is ignored and the status bar says it did not hit the ground or a surface

#### Scenario: Click above the horizon with a reference corner
- **GIVEN** a reference corner with the X reference plane selected
- **WHEN** the user clicks a point of the photo above the horizon that lies on that facade
- **THEN** the click lands on the X reference plane

### Requirement: Reference corner for photos without a floor
The add-on SHALL let the user set a reference corner by clicking a vertical edge in the photo and entering an assumed distance from camera A, SHALL offer two vertical reference planes through that corner (along X and along Y) of which one is selected, and SHALL state in the panel that the scale is assumed while the reference corner is in use.

#### Scenario: Facade seen from below
- **GIVEN** a worm's-eye photo with no ground visible and a reference corner set on the building's corner at 10 m
- **WHEN** the user builds a wall with the Wall tool on the facade along X
- **THEN** the wall lies in the X reference plane and its edges project onto the clicked pixels within 2 px through camera A

#### Scenario: Changing the assumed distance
- **WHEN** the user changes the assumed distance of the reference corner from 10 m to 20 m before building
- **THEN** walls built afterwards are twice as far and twice as large, and their outline through camera A is the same

#### Scenario: Scale is reported as assumed
- **WHEN** a reference corner is set
- **THEN** the Blockout panel shows that the scale comes from an assumed distance

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
The Box tool SHALL create an axis-aligned box from two opposite footprint corners and a third click, standing on the surface the footprint was clicked on; on a horizontal base the third click gives the height, and on a vertical base (a wall or a reference plane) it gives the depth the box extends out of that surface.

#### Scenario: Bench
- **WHEN** the user clicks two opposite floor corners of a bench and then its top edge
- **THEN** a box exists whose footprint corners and top edge project onto the clicked pixels within 2 px through camera A

#### Scenario: Balcony on a facade
- **GIVEN** a wall or reference plane along X
- **WHEN** the user clicks two opposite corners of a balcony's back on that facade and then its front edge
- **THEN** a box exists whose back face lies in the facade and whose front edge projects onto the clicked pixel within 2 px through camera A

### Requirement: Box from its near edge
A Box from Edge tool SHALL create an axis-aligned box on a horizontal base from three clicks: a near bottom corner, the top of that vertical edge, and the opposite top corner, for objects whose far footprint corner is hidden.

#### Scenario: Furniture against a wall
- **GIVEN** a bench standing on the floor against a wall, so the far corner of its footprint is hidden behind it
- **WHEN** the user clicks the bench's near bottom corner on the floor, the top of that vertical edge, and the opposite top corner
- **THEN** a box exists from the floor to the bench's top whose three clicked points project onto their pixels within 2 px through camera A

#### Scenario: Vertical base refused
- **WHEN** the first click lands on a wall
- **THEN** no box is created and the message asks for a corner on a floor or a box top

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
