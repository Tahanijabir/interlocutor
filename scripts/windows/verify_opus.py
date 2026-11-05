
"""Functional tests for native Opus through opuslib-next."""

import math
import random
import struct
import unittest

import opuslib_next as opus


def generate_pcm(sample_rate, channels, frame_ms, signal, frame_index=0):
    """Generate deterministic 16-bit interleaved PCM audio."""
    samples_per_channel = sample_rate * frame_ms // 1000
    rng = random.Random(12345 + frame_index)
    samples = []

    for i in range(samples_per_channel):
        t = (frame_index * samples_per_channel + i) / sample_rate

        if signal == "silence":
            value = 0
        elif signal == "tone_440":
            value = int(10000 * math.sin(2 * math.pi * 440 * t))
        elif signal == "tone_1800":
            value = int(10000 * math.sin(2 * math.pi * 1800 * t))
        elif signal == "noise":
            value = rng.randint(-10000, 10000)
        else:
            raise ValueError(f"Unknown signal: {signal}")

        for channel in range(channels):
            samples.append(value if channel == 0 else value // 2)

    return struct.pack(f"<{len(samples)}h", *samples)


def create_codec(sample_rate, channels, bitrate, vbr):
    encoder = opus.Encoder(
        fs=sample_rate,
        channels=channels,
        application=opus.APPLICATION_VOIP,
    )
    decoder = opus.Decoder(
        fs=sample_rate,
        channels=channels,
    )

    encoder.bitrate = bitrate
    encoder.vbr = int(vbr)

    return encoder, decoder


class OpusFunctionalTests(unittest.TestCase):

    def check_round_trip(
        self, sample_rate, channels, frame_ms,
        bitrate, vbr, signal
    ):
        encoder, decoder = create_codec(
            sample_rate, channels, bitrate, vbr
        )

        samples_per_channel = sample_rate * frame_ms // 1000

        pcm = generate_pcm(
            sample_rate, channels, frame_ms, signal
        )

        packet = encoder.encode(pcm, samples_per_channel)
        decoded = decoder.decode(packet, samples_per_channel)

        self.assertIsInstance(packet, bytes)
        self.assertGreater(len(packet), 0)
        self.assertEqual(len(decoded), len(pcm))

        if signal != "silence":
            decoded_samples = struct.unpack(
                f"<{len(decoded) // 2}h", decoded
            )
            self.assertGreater(
                max(abs(x) for x in decoded_samples),
                100,
                "Decoded signal amplitude is unexpectedly low.",
            )

    def test_audio_signals(self):
        """Test silence, multiple tones, and deterministic noise."""
        signals = (
            "silence",
            "tone_440",
            "tone_1800",
            "noise",
        )

        for signal in signals:
            with self.subTest(signal=signal):
                self.check_round_trip(
                    sample_rate=48000,
                    channels=1,
                    frame_ms=40,
                    bitrate=16000,
                    vbr=False,
                    signal=signal,
                )

    def test_codec_configurations(self):
        """Test sample rates, frame sizes, channels, and bitrate modes."""
        configurations = (
            ("project_48k_40ms_cbr", 48000, 1, 40, 16000, False),
            ("low_latency_20ms", 48000, 1, 20, 16000, False),
            ("sample_rate_16k", 16000, 1, 40, 16000, False),
            ("vbr_48k", 48000, 1, 40, 16000, True),
            ("stereo_48k", 48000, 2, 20, 32000, False),
        )

        for name, rate, channels, duration, bitrate, vbr in configurations:
            with self.subTest(configuration=name):
                self.check_round_trip(
                    sample_rate=rate,
                    channels=channels,
                    frame_ms=duration,
                    bitrate=bitrate,
                    vbr=vbr,
                    signal="tone_440",
                )

    def test_continuous_stream(self):
        """Test multiple frames with persistent codec state."""
        sample_rate = 48000
        channels = 1
        frame_ms = 40
        frame_samples = sample_rate * frame_ms // 1000

        encoder, decoder = create_codec(
            sample_rate, channels, 16000, False
        )

        signals = (
            "tone_440",
            "tone_440",
            "tone_1800",
            "noise",
            "silence",
            "tone_440",
            "noise",
            "tone_1800",
        )

        non_silent_frames = 0

        for frame_index, signal in enumerate(signals):
            with self.subTest(frame=frame_index, signal=signal):
                pcm = generate_pcm(
                    sample_rate,
                    channels,
                    frame_ms,
                    signal,
                    frame_index,
                )

                packet = encoder.encode(pcm, frame_samples)
                decoded = decoder.decode(packet, frame_samples)

                self.assertGreater(len(packet), 0)
                self.assertEqual(len(decoded), len(pcm))

                if signal != "silence" and any(decoded):
                    non_silent_frames += 1

        self.assertGreaterEqual(non_silent_frames, 6)


if __name__ == "__main__":
    unittest.main(verbosity=2)
