from music21 import converter, note, meter, key
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

gt_path = BASE_DIR / "ground_truth" / "M01.mxl"
pred_path = BASE_DIR / "audiveris_output" / "M01_original.mxl"


def inspect_musicxml(path):
    print("=" * 60)
    print("FILE:", path.name)

    score = converter.parse(path)

    notes = list(score.recurse().notes)
    rests = list(score.recurse().getElementsByClass(note.Rest))
    measures = list(score.recurse().getElementsByClass("Measure"))
    time_signatures = list(score.recurse().getElementsByClass(meter.TimeSignature))
    key_signatures = list(score.recurse().getElementsByClass(key.KeySignature))

    print("Measures:", len(measures))
    print("Notes:", len(notes))
    print("Rests:", len(rests))

    if time_signatures:
        print("Time Signature:", time_signatures[0].ratioString)

    if key_signatures:
        print("Key Signature sharps:", key_signatures[0].sharps)

    print("\nFirst 10 notes:")

    for n in notes[:10]:
        if isinstance(n, note.Note):
            print(
                n.pitch.nameWithOctave,
                "duration:",
                n.duration.quarterLength
            )


inspect_musicxml(gt_path)
inspect_musicxml(pred_path)