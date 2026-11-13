# Spec Delta

## Purpose

Project the calibrated photo from the fixed projection camera (camera A) onto geometry, and provide a separate render camera (camera B) that can move to show parallax.

## ADDED Requirements

### Requirement: Project requires a calibrated camera
The Project action SHALL be available only when a calibrated camera A and its photo exist; otherwise it SHALL be disabled with a hint to run Calibrate first.

#### Scenario: No calibration yet
- **WHEN** the user opens the panel in a scene without camera A
- **THEN** the Project button is disabled and the panel says to calibrate first

### Requirement: Default projection plane
When no mesh is selected, Project SHALL create a plane perpendicular to camera A's view direction whose width-to-height ratio equals the photo's and whose edges exactly match camera A's frame at a user-adjustable distance.

#### Scenario: Plane fills the frame
- **GIVEN** a 4000x3000 photo and nothing selected
- **WHEN** the user presses Project
- **THEN** a plane with a 4:3 ratio is created, and seen through camera A its edges coincide with the camera frame

#### Scenario: Changing the plane distance
- **WHEN** the user changes the projection distance of the plane
- **THEN** the plane moves along camera A's view direction and is resized so it still exactly fills camera A's frame

### Requirement: Projection onto selected meshes
When one or more mesh objects are selected, Project SHALL set up the projection on each selected mesh instead of creating a plane.

#### Scenario: User blockout
- **GIVEN** three selected mesh objects modelled to match the photo
- **WHEN** the user presses Project
- **THEN** each of the three objects shows the photo projected from camera A, and no new plane is created

#### Scenario: Non-mesh in selection
- **WHEN** the selection contains a mesh and a light
- **THEN** only the mesh receives the projection and the panel reports that the light was skipped

### Requirement: Subdivision for correct perspective
Each projected object SHALL receive a non-rounding (simple) subdivision placed before the projection, with a level chosen automatically so that no edge spans more than about 32 pixels of the photo as seen through camera A, capped at level 6, and the level SHALL stay editable.

#### Scenario: No diagonal break on a plane
- **WHEN** the default plane is projected and viewed through camera B at a 30-degree angle to camera A
- **THEN** straight lines in the photo stay straight on the plane, with no bend along triangle diagonals

#### Scenario: Shape is preserved
- **WHEN** a box blockout is projected
- **THEN** its corners stay sharp and its silhouette does not change

### Requirement: UV projection from camera A with photo aspect
Each projected object SHALL get a dedicated projection UV map generated from camera A with the photo's aspect ratio, so that seen through camera A the texture matches the photo pixel for pixel.

#### Scenario: Pixel match through camera A
- **WHEN** the scene is rendered through camera A after Project
- **THEN** the projected geometry inside the frame shows the photo at its original position, scale and proportions

#### Scenario: Non-standard aspect
- **GIVEN** a 1080x1920 portrait photo
- **WHEN** the user presses Project
- **THEN** the projected photo is not squashed or stretched through camera A

#### Scenario: Object moved after projection
- **WHEN** the user moves or rotates a projected object while the projection is live
- **THEN** seen through camera A the object still shows the part of the photo that lies behind it in the frame

### Requirement: Projection material
Projected objects SHALL use a material that shows the photo unaffected by scene lighting, and areas that fall outside camera A's frame SHALL render transparent rather than repeating the photo.

#### Scenario: Lighting does not change the photo
- **WHEN** the user adds a bright light next to the projected plane
- **THEN** the photo's colours through camera A stay as in the original image

#### Scenario: Outside the frame
- **WHEN** part of a projected object lies outside camera A's frame
- **THEN** that part renders transparent and the photo is not tiled onto it

### Requirement: Render camera B
Project SHALL create camera B as a copy of camera A (same position, rotation and lens) when it does not exist yet, set camera B as the scene's active camera, and leave camera A in place as the projector.

#### Scenario: First projection
- **WHEN** the user presses Project for the first time
- **THEN** a camera B exists at camera A's pose, it is the active scene camera, and camera A is unchanged

#### Scenario: Camera B already exists
- **GIVEN** camera B has been moved by the user
- **WHEN** the user presses Project again on another object
- **THEN** camera B keeps its current position and no extra camera is created

#### Scenario: Moving camera B shows parallax
- **GIVEN** a projected plane and a 3D object placed in front of it
- **WHEN** camera B moves sideways
- **THEN** the 3D object shifts relative to the projected photo, while the photo stays fixed on the plane

### Requirement: Single undo step
Project SHALL be undoable in one undo step.

#### Scenario: Undo Project
- **WHEN** the user presses Project and then Ctrl+Z once
- **THEN** the created plane, modifiers, material and camera B are gone and the scene is as before Project
