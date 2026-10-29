# Style samples (for Reed's approval)

Each style starts switched off. Before Reed switches one on, we make one small sample in it and Reed looks at it (spec, feature 2). This is the cheapest sample that shows a style across our whole pipeline: one character sheet, one storyboard still and one short clip, all of the same moment, so the styles can be compared side by side. Nothing here runs until Reed approves it; every run is logged in ops/SPEND.md.

**The moment, the same in every style:** Tasha (a dog owner) kneels in a bright kitchen and pours Iron Paws into the bowl, then grins. The Skeleton sample uses a skeleton as the lead, since that is the whole style. No Claude call: the sheet prompt is the server's own, and the still and clip prompts below are written out in full, so the price is exact.

**Price, at 1 credit = $0.1028:** a sheet is 1.50 credits (Nano Banana Pro), a still 0.33 (Nano Banana 2.1), a 4-second clip at 480p 4 (Seedance 2.5, its shortest). One sample is **5.83 credits (about $0.60)**. All 10 that can run now: **58.30 credits (about $5.99)**. A sheet that fails its look check can be remade once for 1.50 more; that is only spent if it happens.

**What Reed checks:** does it look like the style; does Tasha read as an adult woman, the same person in the sheet, the still and the clip; is the bag's label right; did anything get refused (Flow-QA asked us to watch copyright refusals on the Pixar styles).

| Style | Credits | What |
|---|---|---|
| Disney Pixar | 5.83 | 1 sheet + 1 still + one 4 s clip |
| Song | 5.83 | 1 sheet + 1 still + one 4 s clip |
| Zack D | 5.83 | 1 sheet + 1 still + one 4 s clip |
| Skeleton | 5.83 | 1 sheet + 1 still + one 4 s clip |
| Claymation | 5.83 | 1 sheet + 1 still + one 4 s clip |
| Anime comic | 5.83 | 1 sheet + 1 still + one 4 s clip |
| Paper | 5.83 | 1 sheet + 1 still + one 4 s clip |
| Watercolor | 5.83 | 1 sheet + 1 still + one 4 s clip |
| Wool crochet | 5.83 | 1 sheet + 1 still + one 4 s clip |
| Whiteboard | not yet | needs its own flow first (spec) |
| Vox | 5.83 | 1 sheet + 1 still + one 4 s clip |
| Podcast | not yet | needs its own flow first (spec) |

## The exact tests

### Disney Pixar

1. **Sheet** (Nano Banana Pro, 1.50 credits), the server's own prompt for this style:

```
Generate a character turnaround sheet of one character on a plain light grey background: exactly three full-body views of the same character side by side at the same scale, left to right a front view, a side view in profile and a back view; all three views are always there. Standing in a neutral pose with a calm expression. A frame in the style of a Pixar animated feature film: high-end stylised 3D animation, every surface a designed 3D asset with simplified, appealing shapes and believable stylised materials, never photographic texture. Caricatured, appealing design with a readable silhouette and a face built from clear, simple masses: large expressive eyes with glossy catch-lights, defined expressive eyebrows, a simplified nose and a wide expressive mouth; smooth skin with soft subsurface warmth and a subtle matte finish; hair sculpted into clear stylised clumps and locks, never fine strands. The body and face follow the character's age: an adult has an adult's height, build and face (a defined jaw, the head only slightly large for the body), never a child's; a teenager looks like a teenager, a child like a child. An animal is a stylised Pixar animal: simplified appealing shapes and the same glossy eyes. One fixed outfit with simplified, believable fabric folds, identical in every view, and one silhouette-defining item that reads at a glance. Even, soft studio light, no shadows on the background. An original character: never one that resembles a famous film, TV, comic or game character, with no signature costume, hairstyle or prop of one. No text, letters, names, labels, logos or numbers anywhere in the image. The character: Mid-30s woman, a dog owner and nurse; warm brown skin, dark curly hair in a high puff, a mustard cardigan over a white T-shirt, blue jeans.
```

2. **Still** (Nano Banana 2.1, 0.33 credits), with the approved sheet as image 1 and the Iron Paws peanut butter bag as image 2:

```
Generate a still of Tasha from image 1 in a bright kitchen: medium shot at eye level, Tasha kneeling by a dog bowl with a big hopeful smile, the Iron Paws peanut butter bag from image 2 on the floor beside the bowl, label facing the camera; keep its shape, label, logo and colours completely unchanged. A frame in the style of a Pixar animated feature film: high-end stylised 3D animation in which every object and surface is a designed, stylised 3D asset with simplified, appealing shapes. Faces, builds and outfits come from the character sheets. Rich cinematic lighting with soft global illumination, warm bounce light and gentle colour in the shadows, a detailed lived-in environment with believable stylised materials, shallow cinematic depth of field, and saturated but harmonious colour. Composed like a hero frame from an animated feature, with the camera inside the scene at a cinematic angle and the scene filling the entire frame. Expressions are big and readable with the sound off.
```

3. **Clip** (Seedance 2.5, 480p, 4 s, 4 credits), with the still, the sheet and the bag as reference images:

```
Audio: no one speaks (no voices, narration or dialogue), only a quiet kitchen hum. No music, background music, BGM, score, instrumental, melody, synth effects, ambient pad, drone, swelling tone or stinger. No subtitles.
References: [Image1] is the first frame. It sets the opening composition only; the character sheet sets the face and outfit and overrides the first frame where they differ. [Image2] is Tasha. [Image3] is the Iron Paws peanut butter bag.
Summary: Tasha pours a scoop into the bowl and beams.
Style: Smooth cinematic 3D animation in the style of a Pixar feature film, fluid and expressive, with soft global light, warm bounce light and saturated but harmonious colour.
Setting: a bright kitchen in morning light.
Shots (hard cuts):
Shot 1 | 0-2 s. Medium shot, slow push in. Tasha tips a scoop from the bag into the bowl. No one speaks.
Shot 2 | 2-4 s. Close-up, static. Tasha looks up with a big, delighted grin. No one speaks.
Keep: Tasha's identity and look stable in every shot, as in [Image2]; the bag as [Image3], label to camera.
Audio: no one speaks (no voices, narration or dialogue), only a quiet kitchen hum. No music, background music, BGM, score, instrumental, melody, synth effects, ambient pad, drone, swelling tone or stinger. No subtitles.
```

### Song

1. **Sheet** (Nano Banana Pro, 1.50 credits), the server's own prompt for this style:

```
Generate a character turnaround sheet of one character on a plain light grey background: exactly three full-body views of the same character side by side at the same scale, left to right a front view, a side view in profile and a back view; all three views are always there. Standing in a neutral pose with a calm expression. A frame in the style of a Pixar animated feature film: high-end stylised 3D animation, every surface a designed 3D asset with simplified, appealing shapes and believable stylised materials. Caricatured, appealing design with a readable silhouette: large expressive eyes with glossy catch-lights, defined eyebrows, a wide expressive mouth, smooth matte skin, hair sculpted into clear stylised clumps. The body and face follow the character's age: an adult has an adult's height, build and face (a defined jaw, the head only slightly large for the body), never a child's; a teenager looks like a teenager, a child like a child. An animal is a stylised Pixar animal with the same glossy eyes. One fixed, stage-ready outfit with one bold colour that reads at a glance, identical in every view. Even, soft studio light, no shadows on the background. An original character: never one that resembles a famous film, TV, comic or game character, with no signature costume, hairstyle or prop of one. No text, letters, names, labels, logos or numbers anywhere in the image. The character: Mid-30s woman, a dog owner and nurse; warm brown skin, dark curly hair in a high puff, a mustard cardigan over a white T-shirt, blue jeans.
```

2. **Still** (Nano Banana 2.1, 0.33 credits), with the approved sheet as image 1 and the Iron Paws peanut butter bag as image 2:

```
Generate a still of Tasha from image 1 in a bright kitchen: medium shot at eye level, Tasha kneeling by a dog bowl with a big hopeful smile, the Iron Paws peanut butter bag from image 2 on the floor beside the bowl, label facing the camera; keep its shape, label, logo and colours completely unchanged. A frame in the style of an animated Pixar musical: high-end stylised 3D animation, every object a designed 3D asset with simplified, appealing shapes. Faces, builds and outfits come from the character sheets. Music-video light: saturated, harmonious colour, warm bounce light with a coloured rim light, a soft haze catching the light, shallow cinematic depth of field. Composed like a hero frame from an animated feature, the camera inside the scene and the scene filling the frame. Expressions and poses are big and full of rhythm, readable with the sound off.
```

3. **Clip** (Seedance 2.5, 480p, 4 s, 4 credits), with the still, the sheet and the bag as reference images:

```
Audio: no one speaks (no voices, narration or dialogue), only a quiet kitchen hum. No music, background music, BGM, score, instrumental, melody, synth effects, ambient pad, drone, swelling tone or stinger. No subtitles.
References: [Image1] is the first frame. It sets the opening composition only; the character sheet sets the face and outfit and overrides the first frame where they differ. [Image2] is Tasha. [Image3] is the Iron Paws peanut butter bag.
Summary: Tasha pours a scoop into the bowl and beams.
Style: Smooth cinematic 3D animation in the style of an animated Pixar musical, fluid and full of rhythm, saturated music-video light with a coloured rim light and soft haze.
Setting: a bright kitchen in morning light.
Shots (hard cuts):
Shot 1 | 0-2 s. Medium shot, slow push in. Tasha tips a scoop from the bag into the bowl. No one speaks.
Shot 2 | 2-4 s. Close-up, static. Tasha looks up with a big, delighted grin. No one speaks.
Keep: Tasha's identity and look stable in every shot, as in [Image2]; the bag as [Image3], label to camera.
Audio: no one speaks (no voices, narration or dialogue), only a quiet kitchen hum. No music, background music, BGM, score, instrumental, melody, synth effects, ambient pad, drone, swelling tone or stinger. No subtitles.
```

### Zack D

1. **Sheet** (Nano Banana Pro, 1.50 credits), the server's own prompt for this style:

```
Generate a character turnaround sheet of one character on a plain light grey background: exactly three full-body views of the same character side by side at the same scale, left to right a front view, a side view in profile and a back view; all three views are always there. Standing in a neutral pose with a calm expression. Friendly stylised 3D animation in the Pixar register: rounded, simplified forms, soft even light, a clean readable silhouette and large expressive eyes. The body and face follow the character's age: an adult has an adult's height, build and face (a defined jaw, adult proportions), never a child's; a teenager looks like a teenager, a child like a child. One fixed, simple outfit in one clear colour, identical in every view, and one silhouette-defining item that reads at a glance. Even, soft studio light, no shadows on the background. An original character: never one that resembles a famous film, TV, comic or game character, with no signature costume, hairstyle or prop of one. No text, letters, names, labels, logos or numbers anywhere in the image. The character: Mid-30s woman, a dog owner and nurse; warm brown skin, dark curly hair in a high puff, a mustard cardigan over a white T-shirt, blue jeans.
```

2. **Still** (Nano Banana 2.1, 0.33 credits), with the approved sheet as image 1 and the Iron Paws peanut butter bag as image 2:

```
Generate a still of Tasha from image 1 in a bright kitchen: medium shot at eye level, Tasha kneeling by a dog bowl with a big hopeful smile, the Iron Paws peanut butter bag from image 2 on the floor beside the bowl, label facing the camera; keep its shape, label, logo and colours completely unchanged. Friendly stylised 3D animation in the Pixar register, rounded forms and soft even light. Faces, builds and outfits come from the character sheets. The world is a bright cyan field with a soft horizon that continues past every edge of the frame, the camera inside it; no walls, ceiling or edge where the ground ends; the ground smooth. The subject is centred or deliberately placed, resting naturally with one soft contact shadow, with generous clean background around it. Only the product is photoreal.
```

3. **Clip** (Seedance 2.5, 480p, 4 s, 4 credits), with the still, the sheet and the bag as reference images:

```
Audio: no one speaks (no voices, narration or dialogue), only a quiet kitchen hum. No music, background music, BGM, score, instrumental, melody, synth effects, ambient pad, drone, swelling tone or stinger. No subtitles.
References: [Image1] is the first frame. It sets the opening composition only; the character sheet sets the face and outfit and overrides the first frame where they differ. [Image2] is Tasha. [Image3] is the Iron Paws peanut butter bag.
Summary: Tasha pours a scoop into the bowl and beams.
Style: Friendly stylised 3D animation in the Pixar register, rounded forms and soft even light, in a bright cyan world that continues past every edge of the frame.
Setting: a bright kitchen in morning light.
Shots (hard cuts):
Shot 1 | 0-2 s. Medium shot, slow push in. Tasha tips a scoop from the bag into the bowl. No one speaks.
Shot 2 | 2-4 s. Close-up, static. Tasha looks up with a big, delighted grin. No one speaks.
Keep: Tasha's identity and look stable in every shot, as in [Image2]; the bag as [Image3], label to camera.
Audio: no one speaks (no voices, narration or dialogue), only a quiet kitchen hum. No music, background music, BGM, score, instrumental, melody, synth effects, ambient pad, drone, swelling tone or stinger. No subtitles.
```

### Skeleton

1. **Sheet** (Nano Banana Pro, 1.50 credits), the server's own prompt for this style:

```
Generate a character turnaround sheet of one character on a plain light grey background: exactly three full-body views of the same character side by side at the same scale, left to right a front view, a side view in profile and a back view; all three views are always there. Standing in a neutral pose with a calm expression. Cinematic 3D animated render. A skeleton character (the description says so) is a full anatomical skeleton with natural adult human proportions, tall and lanky, smooth ivory-cream bones with realistic bone detail (not toy-smooth, not chibi, not scary), and large expressive cartoon eyes with white sclera and dark pupils set in the eye sockets: an emotive, lovable face; it wears nothing unless the description dresses it, and then wears that one outfit with the skull and hands still showing. Anyone else is a stylised 3D cartoon human whose body and face follow their age: an adult has an adult's height, build and face, never a child's. One fixed look, identical in every view. Even, soft studio light, no shadows on the background. An original character: never one that resembles a famous film, TV, comic or game character, with no signature costume, hairstyle or prop of one. No text, letters, names, labels, logos or numbers anywhere in the image. The character: A skeleton, the story's lead (the 'you' the narrator talks to); no clothes.
```

2. **Still** (Nano Banana 2.1, 0.33 credits), with the approved sheet as image 1 and the Iron Paws peanut butter bag as image 2:

```
Generate a still of the skeleton from image 1 in a bright kitchen: medium shot at eye level, the skeleton kneeling by a dog bowl with a big hopeful smile, the Iron Paws peanut butter bag from image 2 on the floor beside the bowl, label facing the camera; keep its shape, label, logo and colours completely unchanged. Cinematic 3D animated render: a photoreal environment for the story's world, a warm colour grade, soft volumetric light with drifting atmosphere, shallow depth of field. The skeleton and everyone else come from the character sheets: the same ivory, cartoon-eyed skeleton in every shot. Its eyes and posture carry the feeling, big and readable with the sound off.
```

3. **Clip** (Seedance 2.5, 480p, 4 s, 4 credits), with the still, the sheet and the bag as reference images:

```
Audio: no one speaks (no voices, narration or dialogue), only a quiet kitchen hum. No music, background music, BGM, score, instrumental, melody, synth effects, ambient pad, drone, swelling tone or stinger. No subtitles.
References: [Image1] is the first frame. It sets the opening composition only; the character sheet sets the face and outfit and overrides the first frame where they differ. [Image2] is the skeleton. [Image3] is the Iron Paws peanut butter bag.
Summary: The skeleton pours a scoop into the bowl and beams.
Style: Cinematic 3D animation, the same ivory cartoon-eyed skeleton in every shot, its bones moving with natural weight, photoreal environment, warm grade, soft volumetric light.
Setting: a bright kitchen in morning light.
Shots (hard cuts):
Shot 1 | 0-2 s. Medium shot, slow push in. The skeleton tips a scoop from the bag into the bowl. No one speaks.
Shot 2 | 2-4 s. Close-up, static. The skeleton looks up with a big, delighted grin. No one speaks.
Keep: the skeleton's identity and look stable in every shot, as in [Image2]; the bag as [Image3], label to camera.
Audio: no one speaks (no voices, narration or dialogue), only a quiet kitchen hum. No music, background music, BGM, score, instrumental, melody, synth effects, ambient pad, drone, swelling tone or stinger. No subtitles.
```

### Claymation

1. **Sheet** (Nano Banana Pro, 1.50 credits), the server's own prompt for this style:

```
Generate a character turnaround sheet of one character on a plain light grey background: exactly three full-body views of the same character side by side at the same scale, left to right a front view, a side view in profile and a back view; all three views are always there. Standing in a neutral pose with a calm expression. Detailed cinematic claymation: a hand-sculpted plasticine character with an appealing idealized build and richly sculpted features: large almond eyes with white clearly visible around a deeply coloured iris, a dark sculpted upper lash line, thick sculpted brows, defined cheekbones and jaw, a neat sculpted nose and softly sculpted lips; matte clay skin showing thumb-worked smoothing and fine tool striations; sculpted hair with deep comb grooves; chunky rounded clay hands with no fingernails. No photographic skin, no real hands, no wrinkled realistic faces. The body and face follow the character's age: an adult has an adult's height, build and face, never a child's; a teenager looks like a teenager, a child like a child. One fixed outfit of real woven fabric with stitched seams, identical in every view, and one silhouette-defining item that reads at a glance. Even, soft studio light, no shadows on the background. An original character: never one that resembles a famous film, TV, comic or game character, with no signature costume, hairstyle or prop of one. No text, letters, names, labels, logos or numbers anywhere in the image. The character: Mid-30s woman, a dog owner and nurse; warm brown skin, dark curly hair in a high puff, a mustard cardigan over a white T-shirt, blue jeans.
```

2. **Still** (Nano Banana 2.1, 0.33 credits), with the approved sheet as image 1 and the Iron Paws peanut butter bag as image 2:

```
Generate a still of Tasha from image 1 in a bright kitchen: medium shot at eye level, Tasha kneeling by a dog bowl with a big hopeful smile, the Iron Paws peanut butter bag from image 2 on the floor beside the bowl, label facing the camera; keep its shape, label, logo and colours completely unchanged. Detailed cinematic claymation scene: hand-sculpted plasticine characters and a physical miniature set, matte clay with thumb-worked smoothing and fine tool striations, real woven fabric clothing with stitched seams, photographed with a macro lens at shallow depth of field with strong background bokeh, warm practical light with a soft rim light, the scene filling the frame with the camera inside the miniature world. Faces, builds and outfits come from the character sheets. Everything in frame is plasticine and real fabric: no photographic skin, no real hands, no fingernails.
```

3. **Clip** (Seedance 2.5, 480p, 4 s, 4 credits), with the still, the sheet and the bag as reference images:

```
Audio: no one speaks (no voices, narration or dialogue), only a quiet kitchen hum. No music, background music, BGM, score, instrumental, melody, synth effects, ambient pad, drone, swelling tone or stinger. No subtitles.
References: [Image1] is the first frame. It sets the opening composition only; the character sheet sets the face and outfit and overrides the first frame where they differ. [Image2] is Tasha. [Image3] is the Iron Paws peanut butter bag.
Summary: Tasha pours a scoop into the bowl and beams.
Style: Handmade stop-motion claymation throughout: matte plasticine with visible fingerprints and tool marks, a slightly stuttery 12 fps stop-motion cadence, no motion blur, not CGI.
Setting: a bright kitchen in morning light.
Shots (hard cuts):
Shot 1 | 0-2 s. Medium shot, slow push in. Tasha tips a scoop from the bag into the bowl. No one speaks.
Shot 2 | 2-4 s. Close-up, static. Tasha looks up with a big, delighted grin. No one speaks.
Keep: Tasha's identity and look stable in every shot, as in [Image2]; the bag as [Image3], label to camera.
Audio: no one speaks (no voices, narration or dialogue), only a quiet kitchen hum. No music, background music, BGM, score, instrumental, melody, synth effects, ambient pad, drone, swelling tone or stinger. No subtitles.
```

### Anime comic

1. **Sheet** (Nano Banana Pro, 1.50 credits), the server's own prompt for this style:

```
Generate a character turnaround sheet of one character on a plain light grey background: exactly three full-body views of the same character side by side at the same scale, left to right a front view, a side view in profile and a back view; all three views are always there. Standing in a neutral pose with a calm expression. Original cel-shaded anime illustration: clean, even ink line weight, two-tone cel shading with one shadow tone, flat bright colour fills, a readable silhouette and simple facial proportions with large expressive eyes. An original character: never one that resembles an existing anime, manga or comic character, costume or franchise. The body and face follow the character's age: an adult has an adult's height, build and face, never a child's; a teenager looks like a teenager, a child like a child. One fixed outfit with simple, bold shapes, identical in every view, and one silhouette-defining item that reads at a glance. Even, soft studio light, no shadows on the background. An original character: never one that resembles a famous film, TV, comic or game character, with no signature costume, hairstyle or prop of one. No text, letters, names, labels, logos or numbers anywhere in the image. The character: Mid-30s woman, a dog owner and nurse; warm brown skin, dark curly hair in a high puff, a mustard cardigan over a white T-shirt, blue jeans.
```

2. **Still** (Nano Banana 2.1, 0.33 credits), with the approved sheet as image 1 and the Iron Paws peanut butter bag as image 2:

```
Generate a still of Tasha from image 1 in a bright kitchen: medium shot at eye level, Tasha kneeling by a dog bowl with a big hopeful smile, the Iron Paws peanut butter bag from image 2 on the floor beside the bowl, label facing the camera; keep its shape, label, logo and colours completely unchanged. Original cel-shaded anime frame: clean, even ink lines, two-tone cel shading, flat bright colour, painted background art, a strong key pose and a readable silhouette. Faces, builds and outfits come from the character sheets. Expressions are big and graphic, readable with the sound off.
```

3. **Clip** (Seedance 2.5, 480p, 4 s, 4 credits), with the still, the sheet and the bag as reference images:

```
Audio: no one speaks (no voices, narration or dialogue), only a quiet kitchen hum. No music, background music, BGM, score, instrumental, melody, synth effects, ambient pad, drone, swelling tone or stinger. No subtitles.
References: [Image1] is the first frame. It sets the opening composition only; the character sheet sets the face and outfit and overrides the first frame where they differ. [Image2] is Tasha. [Image3] is the Iron Paws peanut butter bag.
Summary: Tasha pours a scoop into the bowl and beams.
Style: Original cel-shaded anime animation, clean ink lines and two-tone shading, pose-to-pose with purposeful holds and snappy impact frames.
Setting: a bright kitchen in morning light.
Shots (hard cuts):
Shot 1 | 0-2 s. Medium shot, slow push in. Tasha tips a scoop from the bag into the bowl. No one speaks.
Shot 2 | 2-4 s. Close-up, static. Tasha looks up with a big, delighted grin. No one speaks.
Keep: Tasha's identity and look stable in every shot, as in [Image2]; the bag as [Image3], label to camera.
Audio: no one speaks (no voices, narration or dialogue), only a quiet kitchen hum. No music, background music, BGM, score, instrumental, melody, synth effects, ambient pad, drone, swelling tone or stinger. No subtitles.
```

### Paper

1. **Sheet** (Nano Banana Pro, 1.50 credits), the server's own prompt for this style:

```
Generate a character turnaround sheet of one character on a plain light grey background: exactly three full-body views of the same character side by side at the same scale, left to right a front view, a side view in profile and a back view; all three views are always there. Standing in a neutral pose with a calm expression. Layered papercraft: a character built from stacked cardstock, with visible paper thickness on every cut edge, layered cast shadows between the paper planes and real paper grain and fibres, in saturated, high-contrast colour; the face is papercraft with clear, simple features. The body and face follow the character's age: an adult has an adult's height, build and face, never a child's; a teenager looks like a teenager, a child like a child. One fixed outfit of layered card in clear colours, identical in every view, and one silhouette-defining item that reads at a glance. Everything is real physical paper, photographed: no vector art, no frame or board around it. Even, soft studio light, no shadows on the background. An original character: never one that resembles a famous film, TV, comic or game character, with no signature costume, hairstyle or prop of one. No text, letters, names, labels, logos or numbers anywhere in the image. The character: Mid-30s woman, a dog owner and nurse; warm brown skin, dark curly hair in a high puff, a mustard cardigan over a white T-shirt, blue jeans.
```

2. **Still** (Nano Banana 2.1, 0.33 credits), with the approved sheet as image 1 and the Iron Paws peanut butter bag as image 2:

```
Generate a still of Tasha from image 1 in a bright kitchen: medium shot at eye level, Tasha kneeling by a dog bowl with a big hopeful smile, the Iron Paws peanut butter bag from image 2 on the floor beside the bowl, label facing the camera; keep its shape, label, logo and colours completely unchanged. Layered papercraft world: everything built from stacked cardstock with visible paper thickness, deep layered depth between foreground, midground and background paper planes, layered cast shadows, paper quilling details, the camera inside the scene and the paper world extending past every edge of the frame. Faces, builds and outfits come from the character sheets. Everything in frame is real physical paper, photographed: visible grain and fibres, cut edges showing their thickness, real cast shadows, soft studio light.
```

3. **Clip** (Seedance 2.5, 480p, 4 s, 4 credits), with the still, the sheet and the bag as reference images:

```
Audio: no one speaks (no voices, narration or dialogue), only a quiet kitchen hum. No music, background music, BGM, score, instrumental, melody, synth effects, ambient pad, drone, swelling tone or stinger. No subtitles.
References: [Image1] is the first frame. It sets the opening composition only; the character sheet sets the face and outfit and overrides the first frame where they differ. [Image2] is Tasha. [Image3] is the Iron Paws peanut butter bag.
Summary: Tasha pours a scoop into the bowl and beams.
Style: Layered papercraft stop-motion, real cardstock with visible edges and layered shadows, subtle stepped motion with slight frame-to-frame jitter and no motion blur.
Setting: a bright kitchen in morning light.
Shots (hard cuts):
Shot 1 | 0-2 s. Medium shot, slow push in. Tasha tips a scoop from the bag into the bowl. No one speaks.
Shot 2 | 2-4 s. Close-up, static. Tasha looks up with a big, delighted grin. No one speaks.
Keep: Tasha's identity and look stable in every shot, as in [Image2]; the bag as [Image3], label to camera.
Audio: no one speaks (no voices, narration or dialogue), only a quiet kitchen hum. No music, background music, BGM, score, instrumental, melody, synth effects, ambient pad, drone, swelling tone or stinger. No subtitles.
```

### Watercolor

1. **Sheet** (Nano Banana Pro, 1.50 credits), the server's own prompt for this style:

```
Generate a character turnaround sheet of one character on a plain light grey background: exactly three full-body views of the same character side by side at the same scale, left to right a front view, a side view in profile and a back view; all three views are always there. Standing in a neutral pose with a calm expression. Original watercolour illustration painted on cold-press paper: translucent layered pigment, visible paper tooth, softly irregular painted edges, restrained ink accents for the features, preserved white paper around the figure, a controlled palette. No glossy 3D surfaces and no flat vector gradients. The body and face follow the character's age: an adult has an adult's height, build and face, never a child's; a teenager looks like a teenager, a child like a child. One fixed outfit in one clear colour family, identical in every view, and one silhouette-defining item that reads at a glance. Even, soft studio light, no shadows on the background. An original character: never one that resembles a famous film, TV, comic or game character, with no signature costume, hairstyle or prop of one. No text, letters, names, labels, logos or numbers anywhere in the image. The character: Mid-30s woman, a dog owner and nurse; warm brown skin, dark curly hair in a high puff, a mustard cardigan over a white T-shirt, blue jeans.
```

2. **Still** (Nano Banana 2.1, 0.33 credits), with the approved sheet as image 1 and the Iron Paws peanut butter bag as image 2:

```
Generate a still of Tasha from image 1 in a bright kitchen: medium shot at eye level, Tasha kneeling by a dog bowl with a big hopeful smile, the Iron Paws peanut butter bag from image 2 on the floor beside the bowl, label facing the camera; keep its shape, label, logo and colours completely unchanged. Original watercolour animation frame painted on cold-press paper: translucent layered pigment, visible paper tooth, controlled wet-on-wet blooms, softly irregular painted edges, restrained ink accents, preserved negative space and natural pigment granulation. Faces, builds and outfits come from the character sheets. No glossy 3D surfaces and no flat vector gradients.
```

3. **Clip** (Seedance 2.5, 480p, 4 s, 4 credits), with the still, the sheet and the bag as reference images:

```
Audio: no one speaks (no voices, narration or dialogue), only a quiet kitchen hum. No music, background music, BGM, score, instrumental, melody, synth effects, ambient pad, drone, swelling tone or stinger. No subtitles.
References: [Image1] is the first frame. It sets the opening composition only; the character sheet sets the face and outfit and overrides the first frame where they differ. [Image2] is Tasha. [Image3] is the Iron Paws peanut butter bag.
Summary: Tasha pours a scoop into the bowl and beams.
Style: Original watercolour animation, painterly motion only: translucent pigment, soft edges that move gently, recognisable forms held steady.
Setting: a bright kitchen in morning light.
Shots (hard cuts):
Shot 1 | 0-2 s. Medium shot, slow push in. Tasha tips a scoop from the bag into the bowl. No one speaks.
Shot 2 | 2-4 s. Close-up, static. Tasha looks up with a big, delighted grin. No one speaks.
Keep: Tasha's identity and look stable in every shot, as in [Image2]; the bag as [Image3], label to camera.
Audio: no one speaks (no voices, narration or dialogue), only a quiet kitchen hum. No music, background music, BGM, score, instrumental, melody, synth effects, ambient pad, drone, swelling tone or stinger. No subtitles.
```

### Wool crochet

1. **Sheet** (Nano Banana Pro, 1.50 credits), the server's own prompt for this style:

```
Generate a character turnaround sheet of one character on a plain light grey background: exactly three full-body views of the same character side by side at the same scale, left to right a front view, a side view in profile and a back view; all three views are always there. Standing in a neutral pose with a calm expression. Cinematic knitted-yarn figure: a knitted doll with realistic adult proportions and an idealized build, a smooth doll face with only a light knit texture and sweet painted features (painted eyes with soft lashes, painted lips, gentle blush, a few tiny stitched freckles), visible stitch rows across the knitted skin, luxurious styled yarn hair. No real human skin, no chunky chibi toy, no oversized bobblehead, no hyper-detailed stitching on the face. The body and face follow the character's age: an adult has an adult's height, build and face, never a child's; a teenager looks like a teenager, a child like a child. One fixed knitted outfit fitting the body, identical in every view, and one silhouette-defining item that reads at a glance. Even, soft studio light, no shadows on the background. An original character: never one that resembles a famous film, TV, comic or game character, with no signature costume, hairstyle or prop of one. No text, letters, names, labels, logos or numbers anywhere in the image. The character: Mid-30s woman, a dog owner and nurse; warm brown skin, dark curly hair in a high puff, a mustard cardigan over a white T-shirt, blue jeans.
```

2. **Still** (Nano Banana 2.1, 0.33 credits), with the approved sheet as image 1 and the Iron Paws peanut butter bag as image 2:

```
Generate a still of Tasha from image 1 in a bright kitchen: medium shot at eye level, Tasha kneeling by a dog bowl with a big hopeful smile, the Iron Paws peanut butter bag from image 2 on the floor beside the bowl, label facing the camera; keep its shape, label, logo and colours completely unchanged. Cinematic knitted-yarn scene: a miniature world entirely hand-knitted from yarn, rounded crochet-like stitches with visible stitch rows on every surface, photographed like a stop-motion film still, a medium-wide shot from a step back so the subject is fully visible, the subject sharp and the background gently soft, bright natural daylight, a warm naturalistic palette lifted with real colour. Faces, builds and outfits come from the character sheets. Camera at eye level, inside the scene; everything in frame is knitted yarn, with real cast shadows. No real humans and no photographic skin.
```

3. **Clip** (Seedance 2.5, 480p, 4 s, 4 credits), with the still, the sheet and the bag as reference images:

```
Audio: no one speaks (no voices, narration or dialogue), only a quiet kitchen hum. No music, background music, BGM, score, instrumental, melody, synth effects, ambient pad, drone, swelling tone or stinger. No subtitles.
References: [Image1] is the first frame. It sets the opening composition only; the character sheet sets the face and outfit and overrides the first frame where they differ. [Image2] is Tasha. [Image3] is the Iron Paws peanut butter bag.
Summary: Tasha pours a scoop into the bowl and beams.
Style: Handmade stop-motion knitted-yarn animation throughout, visible stitch rows and soft yarn fibre on every surface, a slightly stuttery 12 fps stop-motion cadence, no motion blur, not CGI.
Setting: a bright kitchen in morning light.
Shots (hard cuts):
Shot 1 | 0-2 s. Medium shot, slow push in. Tasha tips a scoop from the bag into the bowl. No one speaks.
Shot 2 | 2-4 s. Close-up, static. Tasha looks up with a big, delighted grin. No one speaks.
Keep: Tasha's identity and look stable in every shot, as in [Image2]; the bag as [Image3], label to camera.
Audio: no one speaks (no voices, narration or dialogue), only a quiet kitchen hum. No music, background music, BGM, score, instrumental, melody, synth effects, ambient pad, drone, swelling tone or stinger. No subtitles.
```

### Vox

1. **Sheet** (Nano Banana Pro, 1.50 credits), the server's own prompt for this style:

```
Generate a character turnaround sheet of one character on a plain light grey background: exactly three full-body views of the same character side by side at the same scale, left to right a front view, a side view in profile and a back view; all three views are always there. Standing in a neutral pose with a calm expression. Original editorial collage: a character as a paper cutout figure with crisp scissor-cut edges and a soft drop shadow, a clean graphic treatment with one accent colour. The body and face follow the character's age: an adult has an adult's height, build and face, never a child's; a teenager looks like a teenager, a child like a child. One fixed outfit, identical in every view, and one silhouette-defining item that reads at a glance. Even, soft studio light, no shadows on the background. An original character: never one that resembles a famous film, TV, comic or game character, with no signature costume, hairstyle or prop of one. No text, letters, names, labels, logos or numbers anywhere in the image. The character: Mid-30s woman, a dog owner and nurse; warm brown skin, dark curly hair in a high puff, a mustard cardigan over a white T-shirt, blue jeans.
```

2. **Still** (Nano Banana 2.1, 0.33 credits), with the approved sheet as image 1 and the Iron Paws peanut butter bag as image 2:

```
Generate a still of Tasha from image 1 in a bright kitchen: medium shot at eye level, Tasha kneeling by a dog bowl with a big hopeful smile, the Iron Paws peanut butter bag from image 2 on the floor beside the bowl, label facing the camera; keep its shape, label, logo and colours completely unchanged. Original fast-paced editorial collage frame: the real product photo and paper cutouts in clearly separated layers with soft drop shadows, one accent colour against newsprint neutrals, one claim, one proof image and one arrow or highlight per frame. Faces, builds and outfits come from the character sheets. No publication logos and no copied layouts.
```

3. **Clip** (Seedance 2.5, 480p, 4 s, 4 credits), with the still, the sheet and the bag as reference images:

```
Audio: no one speaks (no voices, narration or dialogue), only a quiet kitchen hum. No music, background music, BGM, score, instrumental, melody, synth effects, ambient pad, drone, swelling tone or stinger. No subtitles.
References: [Image1] is the first frame. It sets the opening composition only; the character sheet sets the face and outfit and overrides the first frame where they differ. [Image2] is Tasha. [Image3] is the Iron Paws peanut butter bag.
Summary: Tasha pours a scoop into the bowl and beams.
Style: Original fast-paced editorial collage animation: planar moves, scale changes, wipes, masks and quick camera pushes on paper layers.
Setting: a bright kitchen in morning light.
Shots (hard cuts):
Shot 1 | 0-2 s. Medium shot, slow push in. Tasha tips a scoop from the bag into the bowl. No one speaks.
Shot 2 | 2-4 s. Close-up, static. Tasha looks up with a big, delighted grin. No one speaks.
Keep: Tasha's identity and look stable in every shot, as in [Image2]; the bag as [Image3], label to camera.
Audio: no one speaks (no voices, narration or dialogue), only a quiet kitchen hum. No music, background music, BGM, score, instrumental, melody, synth effects, ambient pad, drone, swelling tone or stinger. No subtitles.
```

