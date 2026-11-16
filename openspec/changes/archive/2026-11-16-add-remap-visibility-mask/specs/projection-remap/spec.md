# Spec Delta

## MODIFIED Requirements

### Requirement: Baked image is saved
The baked image and its visibility mask SHALL be saved as files in a textures folder next to the .blend file when the file has been saved, and SHALL be packed into the .blend otherwise, so they are not lost on reload.

#### Scenario: Saved .blend
- **GIVEN** the .blend file has been saved to disk
- **WHEN** Remap finishes
- **THEN** a PNG with the object's name and a `_vis` PNG with the object's name exist in the textures folder next to the .blend and the material references both

#### Scenario: Unsaved .blend
- **GIVEN** the .blend file was never saved
- **WHEN** Remap finishes and the user then saves the file
- **THEN** the baked image and the mask are stored inside the .blend

### Requirement: Remap leaves render settings unchanged
Remap SHALL restore the scene's render engine, bake settings, the render visibility of lights and of the projection card, and remove any helper object it created, after baking.

#### Scenario: EEVEE scene
- **GIVEN** the scene uses EEVEE
- **WHEN** Remap finishes
- **THEN** the scene still uses EEVEE with the same settings as before

#### Scenario: Scene with its own lights
- **GIVEN** a scene with a sun light and the frame-filling projection card
- **WHEN** Remap finishes on another object
- **THEN** the sun and the card render exactly as before, and no helper light is left in the scene

## ADDED Requirements

### Requirement: Visibility mask
Remap SHALL bake, for each object, a mask of which parts of its surface camera A sees: a texel counts as hidden when another object stands between it and camera A or when its face points away from camera A. Lights in the scene and the projection card SHALL NOT affect the mask.

#### Scenario: Box behind a box
- **GIVEN** a projected wall with a projected box standing in front of it as seen from camera A
- **WHEN** both are remapped
- **THEN** the wall's mask is black in the box's shadow from camera A and white elsewhere inside the frame

#### Scenario: Back faces
- **GIVEN** a projected box seen from camera A
- **WHEN** it is remapped
- **THEN** the box's mask is black on the faces pointing away from camera A and white on the faces camera A sees

#### Scenario: User lighting ignored
- **GIVEN** the same scene once without lights and once with a strong sun casting shadows across the wall
- **WHEN** the wall is remapped in each
- **THEN** the two masks are the same

### Requirement: Hidden areas show the Hidden input
The remapped material SHALL show the baked photo where the mask is white and a Hidden input where it is black; by default the Hidden input SHALL be a flat colour equal to the median of the visible baked texels, and the user SHALL be able to replace it with any colour or texture. Texels outside camera A's frame SHALL stay transparent.

#### Scenario: Fly-through shows no smeared photo
- **GIVEN** a remapped box whose back faces camera A never saw
- **WHEN** the scene is rendered from camera B looking at the back faces
- **THEN** the back faces show one flat colour close to the box's visible colour, not stretched photo pixels

#### Scenario: Same result through camera A
- **WHEN** the scene is rendered through camera A before and after Remap with the default settings
- **THEN** the two renders match apart from resampling differences

#### Scenario: Custom Hidden texture
- **WHEN** the user links an image texture into the material's Hidden input
- **THEN** that texture appears on the hidden areas and the visible areas still show the photo

### Requirement: Grazing threshold
Remap SHALL offer a grazing threshold, default 0, such that surfaces whose angle to camera A's view rays is below it also count as hidden in the mask.

#### Scenario: Default keeps grazing surfaces
- **GIVEN** a floor seen at a very shallow angle from camera A
- **WHEN** it is remapped with the default threshold 0
- **THEN** its mask is white wherever camera A sees it

#### Scenario: Threshold hides grazing surfaces
- **GIVEN** the same floor
- **WHEN** it is remapped with the threshold raised so that the far part of the floor falls below it
- **THEN** the mask is black on that far part and white on the near part
