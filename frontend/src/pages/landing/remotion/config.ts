/** Hero stage film: 4 scenes of 5 s each, looping. */
export const FILM = { width: 840, height: 680, fps: 30, scene: 150 } as const;
export const FILM_DURATION = FILM.scene * 4;

export const CHAPTERS = ["You push", "Docify reacts", "Docs rewrite", "Ask anything"] as const;
