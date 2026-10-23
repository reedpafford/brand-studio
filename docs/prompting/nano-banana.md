# Prompting Nano Banana (2.1 and Pro)

Official sources only, read 2026-10-23. Every rule links to where it comes from.
- **[Docs]**: Google's Gemini API page "Nano Banana image generation". It holds the prompting guide, best practices and limits.
- **[Blog]**: Google Cloud, *The ultimate Nano Banana prompting guide* (2026-03-06). This page is rendered with JavaScript, so it was read through a fetch-and-summarise tool. Quotes from it are close to the original, not exact.
- **[Replicate]**: the model pages and input schemas we actually call: [2.1][r21] ([schema][r21s]) and [Pro][rpro] ([schema][rpros]).

What we use it for: storyboard frames (one still per clip, which then becomes `[Image1]` for Seedance), character sheets, places and props.

## 1. Prompt structure
- Describe the scene in sentences, not keywords. Text-to-image formula: **subject + action + location/context + composition + style** ([Blog][blog]).
- **With reference images**, the formula is **references + how they relate + the new scene** ([Blog][blog]). Blog example: "Using the attached napkin sketch as the structure and the attached fabric sample as the texture, transform this into a high-fidelity 3D armchair render. Place it in a sun-drenched, minimalist living room."
- Start with a strong verb that names the job: generate, place, change, transform ([Blog][blog]).
- Be very specific, and say what the picture is for. "Create a logo for a high-end, minimalist skincare brand" beats "Create a logo" ([Docs § Best practices][docs]).
- For busy scenes, give step-by-step instructions: "First, create a background… Then, in the foreground, add… Finally, place…" ([Docs § Best practices][docs]).
- Combining images, Google's template: "Create a new image by combining the elements from the provided images. Take the [element from image 1] and place it with/on the [element from image 2]. The final image should be a [description]" ([Docs § Advanced composition][docs]).
- Keeping one image's features exactly, Google's template: "Using the provided images, place [element from image 2] onto [element from image 1]. Ensure that the features of [element from image 1] remain completely unchanged" ([Docs § High-fidelity detail preservation][docs]).

## 2. Reference images: how many keep their likeness
| Model | Total images | Kept with high fidelity | Source |
|---|---|---|---|
| Nano Banana 2.1 | 14 | **up to 4 characters** and up to 10 objects | [Docs § Limitations][docs] |
| Nano Banana Pro | 14 | **5 images** high-fidelity (Replicate: "resemblance of up to 5 people") | [Docs § Limitations][docs], [Replicate Pro][rpro] |

More images than this still go through, but likeness isn't kept for the extras. "Character consistency is generally reliable but not perfect every time" ([Replicate Pro][rpro]).

To protect a critical detail (a face, a logo), Google says to describe it in detail alongside the request ([Docs § High-fidelity detail preservation][docs]).

## 3. Camera, light, look
- Use photo and film terms to control composition: wide-angle shot, macro shot, low-angle perspective, aerial view ([Docs § Best practices][docs]; [Blog][blog]).
- Lighting: name the setup ("three-point softbox", "golden hour backlighting creating long shadows") ([Blog][blog]).
- Materials: be concrete ("navy blue tweed", not "suit jacket") ([Blog][blog]).
- Stylized work: "Describe the artistic style, subject, and medium. Be specific about the visual detail (bold lines, colors, etc.) for consistent results" ([Docs § Stylized illustrations][docs]).

## 4. Text in the picture
- Put the exact words in quotes and describe the font ([Blog][blog]; [Docs § Accurate text in images][docs]).
- For professional text work use Pro ([Docs][docs]).
- Text comes out best if you write the text first, then ask for the image ([Docs § Limitations][docs]).

## 5. Editing a picture
- Say what changes **and** what stays. Template: "Using the provided image, change only the [element] to [new]. Keep everything else in the image exactly the same, preserving the original style, lighting, and composition" ([Docs § Inpainting][docs]; [Blog § Image editing][blog]).
- Make small changes one at a time ("Keep everything the same, but change the character's expression…") ([Docs § Best practices][docs]).
- For character turnarounds, include the images already generated in the next prompt ([Docs § Character consistency: 360 view][docs]).

## 6. Settings (parameters, not prompt words)
- **Aspect ratio.** The default is `match_input_image` ([Replicate schemas][r21s]). "By default, the model matches the output image size to that of your input image" ([Docs § Aspect ratios][docs]). With reference images attached, **always set the aspect ratio**, or the frame takes the shape of the first reference.
- **Resolution**: 1K, 2K or 4K ([Replicate][r21]).
- **Format**: jpg (the default) or png ([Replicate][r21s]).
- **Pro `allow_fallback_model`** sends the job to a *different* model (bytedance/seedream-5) when Pro is busy, and you are charged that model's price ([Replicate Pro][rpro]). The default is false.
- Every output carries a SynthID watermark ([Docs][docs]).

## 7. Known limits and failure modes
- The model doesn't always return the number of images asked for ([Docs § Limitations][docs]).
- Masked edits, big lighting changes and blending many images can leave artifacts ([Replicate Pro][rpro]).
- Best prompt languages include EN ([Docs § Limitations][docs]).

## 8. What NOT to put in the prompt
- **Negatives.** Use "semantic negative prompts": say "an empty, deserted street", not "no cars" ([Docs § Best practices][docs]; [Blog][blog]).
- **Keyword lists** instead of sentences ([Blog][blog]).
- **Aspect ratio or resolution as prompt words.** Set them as parameters (§6). Google's own templates do end with "[Aspect ratio]" ([Docs § Product mockups][docs]), so a mention doesn't hurt. The parameter is what counts.
- **More characters than the model keeps** (§2).

[docs]: https://ai.google.dev/gemini-api/docs/nanobanana
[blog]: https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-nano-banana
[r21]: https://replicate.com/google/nano-banana-2.1
[r21s]: https://replicate.com/google/nano-banana-2.1/api/schema
[rpro]: https://replicate.com/google/nano-banana-pro
[rpros]: https://replicate.com/google/nano-banana-pro/api/schema
