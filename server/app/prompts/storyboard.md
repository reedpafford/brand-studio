# Step: Storyboard frames
<!-- Inputs: <image_model> (name, max reference images, aspect), <assets> (id, kind, name, what it shows), <breakdown> (JSON), optional <per_shot>true</per_shot>. Output: StoryboardFrames. -->

Write one image prompt per clip, for the clip's first shot (or one per shot when <per_shot> is true). Each still becomes the visual anchor for its clip, so it must look exactly like the shot will: the same characters, place, light and framing.

For each frame:
- Pick references: the characters in the shot (their sheets), the place, and the brand screen if the shot shows one. Order them by importance and stay within the image model's limit.
- Write the prompt as one clear picture: shot size and angle, who is where doing what, the expression at its peak (this is a still: catch the face mid-reaction, not neutral), the scene's look (palette, visible light, depth, background people), and the aspect.
- Name references in order as "image 1", "image 2": "the boy from image 1, in the bedroom from image 2".
- A brand screen is "the phone screen shows image 3 exactly: same layout, numbers, colours and logo; nothing added". Keep the screen large and flat-on enough to read.
- Stylized 3D animated feature-film look unless the brand block says otherwise. No captions or text overlays (those are added in post); the only text in frame is what's on a real brand screen.
