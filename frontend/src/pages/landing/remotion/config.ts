/**
 * Hero film timing. Intro (headline builds) plays once; then only the 4 scenes loop
 * (the player seeks back to INTRO when the film ends).
 */
export const FILM = { width: 1920, height: 1080, fps: 30, intro: 45, scene: 150 } as const;
export const FILM_DURATION = FILM.intro + FILM.scene * 4;

/** Stage-only variant (mobile): just the scenes, 16:9. */
export const STAGE = { width: 900, height: 720 } as const;

export const CHAPTERS = ["You push", "Docify reacts", "Docs rewrite", "Ask anything"] as const;

/** Layout of the left column in film pixels (used to place the real HTML buttons over the film). */
export const LAYOUT = {
  left: 120,
  ctaTop: 716,
  ctaHeight: 64,
  chaptersTop: 905,
  chapterWidth: 190,
  chapterGap: 12,
  chapterHeight: 64,
} as const;
