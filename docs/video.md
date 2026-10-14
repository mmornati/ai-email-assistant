# The film

A narrated walk through one morning of the demo mailbox: 38 messages arrive, rules route 27 of them, a model reads the
other ten in two calls, code validates every answer, four requests become tasks, and one message waits for you. Every
figure in it comes from the [demo run](getting-started/demo.md) of the real engine on an invented mailbox.

<div style="container-type:inline-size">
<iframe src="film/?embed=1&amp;lang=en" title="AI Mail Assistant, the film" loading="lazy" allow="fullscreen; autoplay"
        allowfullscreen style="display:block;width:100%;height:calc(56.25cqw + 40px);border:0"></iframe>
</div>

Switch between **English** and **Français** with the language menu under the picture; subtitles have their own button
in the same bar. The film is drawn live in your browser on a canvas, so it stays sharp at any size. You can also
[open it on its own page](film/), or download the MP4 in
[English](assets/video/film.en.mp4) or [French](assets/video/film.fr.mp4).

!!! note "How it is made"
    The voice is synthetic ([Kokoro](https://github.com/hexgrad/kokoro), Apache-2.0 weights), the pictures are drawn
    by `docs/video/film/scenes.js`, and the timing follows the narration in `docs/video/film/script.json`. If the demo
    changes, regenerate `docs/assets/demo/run.json` with `python3 demo/run_demo.py --out docs/assets/demo/run.json`, update the figures in the script and the mail
    list at the top of `scenes.js`, then re-narrate.
