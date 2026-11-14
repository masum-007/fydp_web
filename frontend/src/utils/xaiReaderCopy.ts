/** Reader-first descriptions derived from SAVED class-matched attribution metadata. */
import type { AnalysisResponse, ExplanationMethod, SavedExplanation } from "@/services/api";

type ClassName = "Real" | "Fake";
type RegionInfo = { supporting?: unknown; opposing?: unknown };
const asNames = (value: unknown): string[] => Array.isArray(value)
  ? value.filter((v): v is string => typeof v === "string" && v.trim().length > 0).slice(0, 2)
  : [];
function regions(item: SavedExplanation) {
  const raw = item.interpretation?.regions;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return { supporting: [], opposing: [] };
  const obj = raw as RegionInfo;
  return { supporting: asNames(obj.supporting), opposing: asNames(obj.opposing) };
}
const places: Record<string, string> = {
  "outside estimated face/head regions": "the area just outside the mapped face and head",
  "outside estimated face/head regions (approximate)": "the area just outside the mapped face and head",
  "lower crop / neck-clothing vicinity (approximate)": "the lower part of the portrait near the neck or clothing",
  "upper-head / hairline vicinity (approximate)": "the upper head near the hairline",
  "side-of-head / ear vicinity (approximate)": "the side of the head near the ear",
  "other face area": "other parts of the face",
  "person's left cheek": "the person's left cheek",
  "person's right cheek": "the person's right cheek",
  "person's left eye": "the person's left eye",
  "person's right eye": "the person's right eye",
  "person's left eyebrow": "the person's left eyebrow",
  "person's right eyebrow": "the person's right eyebrow",
  "mouth and chin": "the mouth and chin",
  "jawline": "the jawline",
  "forehead": "the forehead",
  "nose": "the nose",
};
function pretty(label: string): string { return places[label] ?? label.replace(" (approximate)", ""); }
function join(values: string[]): string {
  const unique = [...new Set(values.map(pretty).filter(Boolean))];
  return unique.length <= 1 ? unique[0] ?? "" : `${unique.slice(0, -1).join(", ")} and ${unique[unique.length - 1]}`;
}
export function resultInPlainLanguage(result: Pick<AnalysisResponse, "prediction" | "fake_probability" | "threshold">): string {
  const score = (result.fake_probability * 100).toFixed(1);
  const cutoff = (result.threshold * 100).toFixed(1);
  const lead = result.prediction === "Fake"
    ? `The NeuralEdge AI model classified this image as FAKE. Its combined Fake score (${score}%) reached the ${cutoff}% screening cutoff. This means it found visual patterns associated with its Fake training examples.`
    : `The NeuralEdge AI model classified this image as REAL. Its combined Fake score (${score}%) remained below the ${cutoff}% screening cutoff. The model did not find sufficient Fake-associated signal to flag this image as Fake.`;
  const near = Math.abs(result.fake_probability - result.threshold) <= .05
    ? " The score is close to the cutoff, so the result is borderline." : "";
  return lead + near + (result.prediction === "Real" ? " A Real result is not a guarantee of authenticity." : "");
}
export function methodInPlainLanguage(method: ExplanationMethod, item: SavedExplanation, prediction: ClassName): string {
  const target = item.target_label;
  if (target !== "Fake" && target !== "Real") return "This saved explanation does not record which class it explains, so its highlighted areas cannot be described reliably.";
  if (target !== prediction) return `This saved picture explains an earlier ${target} result, but the current classification is ${prediction}. Run the analysis again for a matching explanation.`;
  if (item.status !== "completed") return "This explanation was not completed for the image.";
  const { supporting, opposing } = regions(item);
  const yes = join(supporting), no = join(opposing);
  if (method === "gradcam") {
    return supporting.length
      ? `For this picture, the four NeuralEdge AI image models reacted most strongly to visual information in ${yes} while assessing ${target}. The warm-colored areas show where the image models were most responsive. These locations help explain the image-model response associated with ${target}, while the final score also combines information from all four models. An investigator can compare the highlighted areas with the original image, including visible edges, textures, and lighting.`
      : `NeuralEdge AI generated a ${target}-category heatmap, but the saved regional analysis did not isolate one clearly named area. Several image details may have contributed together, so no localized defect should be inferred.`;
  }
  if (method === "lime") {
    const lead = supporting.length
      ? `LIME identified sections around ${yes} as supporting NeuralEdge AI's ${target} classification. In this local check, those sections contained visual information that helped favor ${target}.`
      : `LIME did not isolate one clearly named region as the main support for ${target}; several smaller sections may matter together.`;
    const counter = opposing.length ? ` Sections around ${no} pulled the local explanation away from ${target}.` : " No clearly named opposing section was recorded.";
    return lead + counter + " These sections show which areas favored the result and which pushed against it, giving investigators useful places to inspect in the original picture.";
  }
  const lead = supporting.length
    ? `SHAP found that visual details in ${yes} added support for NeuralEdge AI's ${target} result when the image was compared with a softened version of itself.`
    : `SHAP did not isolate one clearly named area as the main support for ${target} in the saved comparison.`;
  const counter = opposing.length ? ` Details in ${no} worked against ${target} in that same comparison.` : " No clearly named opposing area was recorded.";
  return lead + counter + " Together, these locations help explain which image details favored the result compared with the softened reference, and where an investigator can look more closely.";
}
export function methodReadingNote(method: ExplanationMethod): string {
  return {
    gradcam: "Technical note: this averages four individual CNN heatmaps rather than directly explaining the final stacking score. A highlighted region is not a confirmed edit.",
    lime: "Technical note: this approximates the final classifier around the current image. Segment boundaries and emphasis can change between runs.",
    shap: "Technical note: contribution colors are measured relative to a blurred reference, not forensic proof of manipulation.",
  }[method];
}
