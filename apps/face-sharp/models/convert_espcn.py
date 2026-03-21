"""Convert pre-trained ESPCN x3 frozen graph (.pb) to TFLite.

Extracts weights from TF1 frozen graph, rebuilds in Keras,
and converts to TFLite with fixed 50x50 input.

The pre-trained model operates on Y channel (luminance) only.
  Input:  [1, 50, 50, 1] float32 (Y channel, [0,1])
  Output: [1, 150, 150, 1] float32 (Y channel, tanh → clip to [0,1])

Usage:
    python convert_espcn.py <input.pb> <output.tflite>
"""

import sys

import numpy as np
import tensorflow as tf

INPUT_SIZE = 50
UPSCALE_FACTOR = 3


class DepthToSpace(tf.keras.layers.Layer):
    """Pixel-shuffle layer (depth_to_space)."""

    def __init__(self, block_size, **kwargs):
        super().__init__(**kwargs)
        self.block_size = block_size

    def call(self, x):
        return tf.nn.depth_to_space(x, self.block_size)


def extract_weights(pb_path):
    """Extract conv weights and biases from frozen graph."""
    with open(pb_path, "rb") as f:
        graph_def = tf.compat.v1.GraphDef()
        graph_def.ParseFromString(f.read())

    weights = {}
    with tf.compat.v1.Session() as sess:
        tf.import_graph_def(graph_def, name="")
        for name in ["f1", "b1", "f2", "b2", "f3", "b3"]:
            weights[name] = sess.run(
                sess.graph.get_tensor_by_name(f"{name}:0"))

    print("Extracted weights:")
    for name, w in weights.items():
        print(f"  {name}: shape={w.shape}")
    return weights


def build_model(weights):
    """Build Keras model matching the pre-trained architecture."""
    # Architecture: Conv2D(5x5,1→64,ReLU) → Conv2D(3x3,64→32,ReLU)
    #             → Conv2D(3x3,32→9,Tanh) → DepthToSpace(3)
    inputs = tf.keras.Input(shape=(INPUT_SIZE, INPUT_SIZE, 1))
    x = tf.keras.layers.Conv2D(
        64, 5, padding="same", activation="relu", name="conv1")(inputs)
    x = tf.keras.layers.Conv2D(
        32, 3, padding="same", activation="relu", name="conv2")(x)
    x = tf.keras.layers.Conv2D(
        9, 3, padding="same", activation="tanh", name="conv3")(x)
    outputs = DepthToSpace(UPSCALE_FACTOR, name="depth_to_space")(x)
    model = tf.keras.Model(inputs, outputs)

    # Load pre-trained weights
    model.get_layer("conv1").set_weights([weights["f1"], weights["b1"]])
    model.get_layer("conv2").set_weights([weights["f2"], weights["b2"]])
    model.get_layer("conv3").set_weights([weights["f3"], weights["b3"]])

    return model


def convert_to_tflite(model):
    """Convert Keras model to TFLite."""
    input_shape = [1, INPUT_SIZE, INPUT_SIZE, 1]
    concrete_func = tf.function(
        lambda x: model(x, training=False)
    ).get_concrete_function(tf.TensorSpec(input_shape, tf.float32))

    converter = tf.lite.TFLiteConverter.from_concrete_functions(
        [concrete_func])
    return converter.convert()


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <input.pb> <output.tflite>")
        sys.exit(1)

    pb_path = sys.argv[1]
    output_path = sys.argv[2]

    # Extract weights and build model
    weights = extract_weights(pb_path)
    model = build_model(weights)
    model.summary()

    # Convert to TFLite
    tflite_model = convert_to_tflite(model)

    with open(output_path, "wb") as f:
        f.write(tflite_model)

    out_size = INPUT_SIZE * UPSCALE_FACTOR
    print(f"\nSaved TFLite model to {output_path}")
    print(f"  Input:  [1, {INPUT_SIZE}, {INPUT_SIZE}, 1] (Y channel)")
    print(f"  Output: [1, {out_size}, {out_size}, 1] (Y channel)")
    print(f"  Size:   {len(tflite_model) / 1024:.1f} KB")


if __name__ == "__main__":
    main()
