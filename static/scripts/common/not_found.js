/**
 * Initializes a Live2D model in the specified canvas using PIXI.js.
 * @param {HTMLCanvasElement} canvas The canvas element for rendering.
 * @param {string} modelPath The path to the model file (.model3.json).
 */
async function initLive2D(canvas, modelPath) {
    window.app = new PIXI.Application({
        view: canvas,
        autoStart: true,
        transparent: true,
        antialias: true,
    });

    const model = await PIXI.live2d.Live2DModel.from(modelPath);

    // Set the canvas size to the model's native size
    app.renderer.resize(model.width, model.height);

    app.stage.addChild(model);
}