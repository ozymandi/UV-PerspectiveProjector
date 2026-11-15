# camera-calibration Specification

## Purpose

Recover a Blender camera whose focal length, orientation, position and scale match the perspective of a single photo, so 3D content and projections line up with the photo without external tools.

## Requirements

### Requirement: Load a photo for calibration
The add-on SHALL let the user pick an image file (JPEG, PNG, TIFF, EXR, WebP) from the add-on panel and SHALL load it as an image datablock used by all later steps.

#### Scenario: Supported image is loaded
- **WHEN** the user picks a 4000x3000 JPEG in the panel
- **THEN** the image appears in the panel as the current photo with its resolution shown

#### Scenario: Unsupported file
- **WHEN** the user picks a file Blender cannot load as an image
- **THEN** the add-on reports an error and keeps the previous state unchanged

### Requirement: One-click automatic calibration
The add-on SHALL provide a Calibrate action that detects vanishing points in the loaded photo and creates or updates the projection camera (camera A) without any further input.

#### Scenario: Interior or architectural photo
- **GIVEN** a photo with clear straight edges along at least two orthogonal directions
- **WHEN** the user presses Calibrate
- **THEN** camera A exists in the scene, and edges in the photo that are parallel to the scene axes align with those axes when viewed through camera A

#### Scenario: Re-running calibration
- **GIVEN** camera A already exists from a previous calibration
- **WHEN** the user presses Calibrate again
- **THEN** the same camera A is updated in place and no duplicate camera is created

### Requirement: Scene axis convention
The calibrated scene SHALL use Blender's Z-up convention: the vertical direction in the photo maps to the Z axis and the ground plane is the XY plane.

#### Scenario: Vertical edges map to Z
- **WHEN** calibration succeeds on a photo with visible vertical edges
- **THEN** those edges are parallel to the world Z axis as seen through camera A

### Requirement: Swap horizontal axes
The add-on SHALL provide an action that swaps which horizontal direction is X and which is Y (a 90-degree turn about Z) without changing what camera A sees.

#### Scenario: Swap X and Y
- **WHEN** the user presses Swap X/Y after calibration
- **THEN** the world X and Y axes exchange their directions in the photo, and the image through camera A is unchanged

### Requirement: Camera A frame matches the photo
Camera A SHALL show the photo as its background image, and the scene render resolution SHALL equal the photo resolution, so the camera frame and the photo coincide exactly.

#### Scenario: Frame and photo coincide
- **WHEN** calibration finishes for a 4000x3000 photo
- **THEN** the render resolution is 4000x3000 at 100%, the photo is visible as camera A's background, and the photo fills the camera frame with no borders or cropping

### Requirement: Focal length recovery
The add-on SHALL estimate the focal length from the vanishing points, assuming the principal point at the image centre and no lens distortion; when only one finite horizontal vanishing point is available it SHALL use the photo's EXIF focal length, or a user-entered focal length if no EXIF is present.

#### Scenario: Two finite vanishing points
- **WHEN** two orthogonal finite vanishing points are found
- **THEN** camera A's focal length is computed from them

#### Scenario: One vanishing point with EXIF
- **GIVEN** a photo whose second horizontal direction has no finite vanishing point and whose EXIF reports a 35 mm equivalent focal length
- **WHEN** the user presses Calibrate
- **THEN** camera A uses the EXIF focal length and the panel states that the focal length came from EXIF

### Requirement: Default position and scale
Camera A SHALL be placed above the ground plane at a user-adjustable camera height (default 1.6 m), with the world origin on the ground directly in front of the camera.

#### Scenario: Default height
- **WHEN** calibration finishes and the user has not changed the height
- **THEN** camera A's Z location is 1.6 m and the ground plane Z=0 lines up with the floor in the photo

#### Scenario: Changing camera height
- **WHEN** the user sets camera height to 10 m
- **THEN** camera A moves to Z=10 m and the view through camera A is unchanged

### Requirement: Reference distance and origin
The add-on SHALL let the user set the world origin by clicking a point on the photo in the camera view, and SHALL let the user scale the scene by marking two points on the photo along one axis and entering their real distance.

#### Scenario: Origin picked on the photo
- **WHEN** the user picks a floor corner in the photo as origin
- **THEN** the world origin lies at that corner as seen through camera A

#### Scenario: Reference distance
- **WHEN** the user marks the two ends of a 3 m wall along X and enters 3 m
- **THEN** the distance between those points in the scene is 3 m and the view through camera A is unchanged

### Requirement: Confidence and manual fallback
The add-on SHALL report the calibration confidence, and when confidence is below the threshold it SHALL open the manual line editor with vanishing lines pre-placed from the best automatic guess instead of silently producing a camera.

#### Scenario: Low-confidence photo
- **GIVEN** a photo of a forest with no reliable straight edges
- **WHEN** the user presses Calibrate
- **THEN** the panel shows that automatic detection was not confident and the manual line editor opens with lines already placed

### Requirement: Manual vanishing line editor
The add-on SHALL let the user drag the endpoints of two pairs of vanishing lines over the photo in camera A's view, assign each pair to an axis (X, Y or Z), and SHALL update camera A live while dragging.

#### Scenario: Dragging a line endpoint
- **WHEN** the user drags an endpoint of an X line
- **THEN** camera A's orientation and focal length update while dragging and the photo stays aligned with the camera frame

#### Scenario: Entering the editor manually
- **GIVEN** an automatic calibration that succeeded
- **WHEN** the user opens the manual editor
- **THEN** the lines appear at the positions that produced the current camera, and editing them refines that camera

#### Scenario: Degenerate lines
- **WHEN** the user makes the two lines of one pair parallel in the image, or makes the two vanishing points incompatible
- **THEN** the camera keeps its last valid state and the panel shows which pair is invalid

#### Scenario: First calibration cannot be solved
- **GIVEN** a photo with no camera A yet
- **WHEN** the user presses Calibrate and the lines cannot be solved (for example a pair is parallel with Focal length on Auto and no EXIF focal)
- **THEN** camera A is still created as a level placeholder (looking along +Y at the camera height, focal from EXIF or the manual focal field) with the photo as its background, the manual editor shows the photo and the lines through it, and the panel shows which pair is invalid

### Requirement: Calibration is stored in the file
Calibration inputs (photo, vanishing lines, axis assignment, height, origin, reference distance) SHALL be saved with the .blend file so the calibration can be reopened and refined after reloading.

#### Scenario: Reopen after save
- **WHEN** the user saves, closes and reopens the .blend file and opens the manual editor
- **THEN** the lines appear where they were left and camera A is unchanged

### Requirement: Single undo step for calibration
Calibrate SHALL be undoable in one undo step.

#### Scenario: Undo Calibrate
- **WHEN** the user presses Calibrate and then Ctrl+Z once
- **THEN** camera A, its background and the render resolution return to their state before Calibrate

### Requirement: Works out of the box
The add-on SHALL work immediately after installing the single extension file in Blender 4.2 or newer on Windows, macOS and Linux, without manual installation of Python packages or internet access.

#### Scenario: Offline install
- **WHEN** the user installs the extension file on a machine without internet access and presses Calibrate
- **THEN** calibration runs without missing-module errors
