import yaml from "js-yaml";
import type { ClassificationResult, ConditionNode, Rule, TorrentRecord } from "./types";

const SEASON_EPISODE_RE = /\bs\d{1,2}[-_. ]*e\d{1,3}\b/gi;
const SEASON_RE = /\bs\d{1,2}\b/gi;
const VOLUME_RE = /\b(?:vol(?:ume)?|v)[-_. ]?\d{1,3}\b/gi;
const BLURAY_RE = /\b(?:blu[- ]?ray|bdmv|uhd|remux)\b/gi;
const RESOLUTION_RE = /\b(?:720|1080|1440|2160|4320)p\b/gi;
const ADULT_CODE_RE = /\b(?:fc2[-_ ]?ppv[-_ ]?\d{4,7}|[a-z]{2,6}-\d{2,5})\b/i;
const ADULT_HINT_RE = /\b(?:dmm|fc2|carib|heyzo|1pondo|mteam|jav)\b/gi;
const EXCLUDE_MUSIC_TXT_RE = /jieshao|list|info|foo_dr|dr analysis|track|playlist|aucdtect/i;
const VINYL_HINT_RE = /vinyl|lineage/i;
const DR_RE = /\bDR(\d{1,2})\b/i;
const SUBTITLE_ARCHIVE_HINT_RE = /\bass\b|pgs|subtitle|sub\b|\u5B57\u5E55/i;
const DVD_ISO_HINT_RE = /dvdiso|\bdvd\b|480i|480p|720x480|r2j/i;
const MUSIC_DISC_HINT_RE =
  /\b(?:ost|soundtrack|drama[ ._-]?cd|album|single|disc\d*|cd)\b|\u30B5\u30A6\u30F3\u30C9\u30C8\u30E9\u30C3\u30AF|\u30C9\u30E9\u30DEcd|\u7279\u5178cd/i;
const SOFTWARE_ISO_HINT_RE = /\bsetup|installer|game|tool|utility|desktop|accessor/i;

const MIN_BLURAY_ISO_SIZE = 10 * 1024 * 1024 * 1024;

const VIDEO_EXTENSIONS = new Set([".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".ts", ".m2ts", ".vob"]);
const BLURAY_STRUCTURE_EXTENSIONS = new Set([".m2ts", ".bdmv", ".clpi", ".mpls"]);
const DVD_STRUCTURE_EXTENSIONS = new Set([".vob", ".ifo", ".bup"]);
const UNCOMMON_MUSIC_EXTENSIONS = new Set([".dsf", ".dff", ".tak", ".tta", ".wv", ".aiff", ".aif"]);
const MUSIC_EXTENSIONS = new Set([".flac", ".wav", ".ape", ".mp3", ".aac", ".m4a", ".ogg", ".wma", ...UNCOMMON_MUSIC_EXTENSIONS]);
const AUDIOBOOK_EXTENSIONS = new Set([".m4b", ".aax", ".abs"]);
const EBOOK_EXTENSIONS = new Set([".pdf", ".epub", ".mobi", ".azw3", ".djvu", ".chm", ".fb2", ".lit", ".rtf"]);
const COMIC_EXTENSIONS = new Set([".cbz", ".cbr"]);
const IMAGE_EXTENSIONS = new Set([".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tif", ".tiff", ".webp", ".bpg"]);
const ARCHIVE_EXTENSIONS = new Set([".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".tgz"]);
const SOFTWARE_EXTENSIONS = new Set([".exe", ".msi", ".apk", ".dmg", ".pkg", ".deb", ".rpm", ".appimage"]);
const DOCUMENT_EXTENSIONS = new Set([".txt", ".md", ".nfo"]);

const OPERATOR_KEYS = new Set([
  "ext_any",
  "ext_all",
  "name_regex",
  "total_files_gte",
  "total_files_lte",
  "size_gte",
  "feature_gte",
  "feature_eq",
  "ext_count_gte",
  "dominant_extension_in"
]);

interface TorrentFeatures {
  totalFiles: number;
  totalSize: number;
  extCounter: Record<string, number>;
  largestFileSize: number;
  dominantExtension: string;
  seasonEpisodeHits: number;
  seasonHits: number;
  volumeHits: number;
  blurayHits: number;
  resolutionHits: number;
  adultHits: number;
  videoFileCount: number;
}

interface RuleHit {
  ruleId: string;
  priority: number;
  confidence: number;
  kind: string;
  subtype: string;
  reason: string;
  specificity: number;
}

export function parseRuleSet(rawYaml: string): Rule[] {
  const loaded = yaml.load(rawYaml);
  if (!Array.isArray(loaded)) {
    throw new Error("Rule file root must be a YAML list.");
  }

  const rules: Rule[] = loaded.map((item, index) => {
    if (!isObject(item)) {
      throw new Error(`Rule at index ${index} must be an object.`);
    }

    const id = asString(item.id, `Rule index ${index}: id`);
    const priority = asNumber(item.priority, `Rule ${id}: priority`);
    const enabled = asBoolean(item.enabled, `Rule ${id}: enabled`);
    const when = asCondition(item.when, `Rule ${id}: when`);
    const then = asThen(item.then, `Rule ${id}: then`);
    const guards = item.guards === undefined ? undefined : asCondition(item.guards, `Rule ${id}: guards`);

    return { id, priority, enabled, when, then, guards };
  });

  return rules.filter((rule) => rule.enabled).sort((a, b) => b.priority - a.priority);
}

export function classifyRecord(record: TorrentRecord, rules: Rule[]): ClassificationResult {
  const features = extractFeatures(record);
  const hits = evaluateRules(record, features, rules);
  const best = decideBest(hits);
  const matchedRuleIds = hits.map((hit) => hit.ruleId);

  if (best && shouldUseRuleResult(best, features)) {
    return {
      infoHash: record.infoHash,
      torrentName: record.torrentName,
      kind: best.kind,
      subtype: best.subtype,
      confidence: clamp(best.confidence),
      reasons: [best.reason],
      matchedRuleIds,
      traceId: createTraceId(),
      indicators: buildIndicators(features, matchedRuleIds)
    };
  }

  return classifyFallback(record, features);
}

function shouldUseRuleResult(best: RuleHit, features: TorrentFeatures): boolean {
  const isoCount = features.extCounter[".iso"] ?? 0;

  if ((best.subtype === "software_disk_image" || best.subtype === "video_dvd_iso") && isoCount > 1) {
    return false;
  }

  if (best.subtype === "software_disk_image" && isBluray(features)) {
    return false;
  }

  if (best.subtype === "music_uncommon_format" && extCount(features, VIDEO_EXTENSIONS) > 0) {
    return false;
  }

  return true;
}

function classifyFallback(record: TorrentRecord, features: TorrentFeatures): ClassificationResult {
  if (features.totalFiles === 0) {
    return buildFallback(record, features, "unknown", "unknown_empty", 0.2, ["empty file list"]);
  }

  if (isBluray(features)) {
    const subtype = (features.extCounter[".iso"] ?? 0) > 0 ? "video_bluray_iso" : "video_bluray_structure";
    return buildFallback(record, features, "video", subtype, 0.98, ["matched Blu-ray structure signature"]);
  }

  if (extCount(features, DVD_STRUCTURE_EXTENSIONS) > 0) {
    return buildFallback(record, features, "video", "video_dvd_structure", 0.97, ["detected DVD VOB/IFO/BUP files"]);
  }

  const videoCount = extCount(features, VIDEO_EXTENSIONS);
  if (videoCount > 0) {
    const [subtype, confidence, reasons] = classifyVideo(features, videoCount);
    return buildFallback(record, features, "video", subtype, confidence, reasons);
  }

  const disk = classifyDiskImage(record, features);
  if (disk) {
    return buildFallback(record, features, disk.kind, disk.subtype, disk.confidence, disk.reasons);
  }

  if (extCount(features, AUDIOBOOK_EXTENSIONS) > 0) {
    return buildFallback(record, features, "audiobook", "audiobook_file", 0.93, ["detected audiobook extensions"]);
  }

  if (extCount(features, MUSIC_EXTENSIONS) > 0) {
    const [subtype, confidence, reasons] = classifyMusic(record);
    return buildFallback(record, features, "music", subtype, confidence, reasons);
  }

  if (extCount(features, COMIC_EXTENSIONS) > 0) {
    return buildFallback(record, features, "comic", "comic_digital", 0.95, ["detected comic-specific archive extensions (.cbz/.cbr)"]);
  }

  const ebookCount = extCount(features, EBOOK_EXTENSIONS);
  if (ebookCount > 0) {
    const subtype = (features.extCounter[".pdf"] ?? 0) > 0 ? "ebook_pdf_collection" : "ebook_collection";
    return buildFallback(record, features, "ebook", subtype, 0.92, ["detected ebook document formats"]);
  }

  if (extCount(features, SOFTWARE_EXTENSIONS) > 0) {
    return buildFallback(record, features, "software", "software_package", 0.97, ["detected executable or installer extensions"]);
  }

  const imageCount = extCount(features, IMAGE_EXTENSIONS);
  if (imageCount > 0 && imageCount === features.totalFiles) {
    return buildFallback(record, features, "image", "image_collection", 0.9, ["all files are image formats"]);
  }

  const archiveCount = extCount(features, ARCHIVE_EXTENSIONS);
  if (archiveCount > 0) {
    if (features.totalFiles === 1 && features.dominantExtension === ".tgz" && SUBTITLE_ARCHIVE_HINT_RE.test(record.torrentName)) {
      return buildFallback(record, features, "archive", "archive_subtitle_pack", 0.88, ["single .tgz archive with subtitle/ASS/PGS markers"]);
    }

    const subtype = features.volumeHits > 0 ? "comic_archive" : "archive_generic";
    const confidence = subtype === "comic_archive" ? 0.86 : 0.75;
    const reason = subtype === "comic_archive" ? "multi-volume archive pattern (Vol.xx)" : "archive formats detected";
    const kind = subtype === "comic_archive" ? "comic" : "archive";
    return buildFallback(record, features, kind, subtype, confidence, [reason]);
  }

  if (extCount(features, DOCUMENT_EXTENSIONS) > 0) {
    return buildFallback(record, features, "document", "document_text", 0.72, ["detected plain text/doc metadata files"]);
  }

  return buildFallback(record, features, "unknown", "unknown_misc", 0.4, ["no strong extension-based signal"]);
}

function buildFallback(record: TorrentRecord, features: TorrentFeatures, kind: string, subtype: string, confidence: number, reasons: string[]): ClassificationResult {
  return {
    infoHash: record.infoHash,
    torrentName: record.torrentName,
    kind,
    subtype,
    confidence: clamp(confidence),
    reasons,
    matchedRuleIds: [],
    traceId: createTraceId(),
    indicators: buildIndicators(features, [])
  };
}

function isBluray(features: TorrentFeatures): boolean {
  if (extCount(features, BLURAY_STRUCTURE_EXTENSIONS) > 0) {
    return true;
  }
  if ((features.extCounter[".iso"] ?? 0) > 0) {
    return features.blurayHits > 0 && features.largestFileSize >= MIN_BLURAY_ISO_SIZE;
  }
  return false;
}

function classifyVideo(features: TorrentFeatures, videoCount: number): [string, number, string[]] {
  const reasons = [`${videoCount} video file(s) detected`];

  if (features.adultHits > 0 && videoCount === 1) {
    reasons.push("adult naming pattern detected");
    return ["video_adult_movie", 0.9, reasons];
  }

  if (features.seasonEpisodeHits >= 2) {
    reasons.push("multiple SxxExx episode patterns detected");
    return ["video_tv_season", 0.95, reasons];
  }

  if (videoCount >= 2 && features.seasonHits >= 1) {
    reasons.push("season markers + multi-file video package");
    return ["video_tv_season", 0.92, reasons];
  }

  if (videoCount === 1 && (features.seasonEpisodeHits >= 1 || features.seasonHits >= 1)) {
    reasons.push("single video with season/episode markers");
    return ["video_tv_episode", 0.84, reasons];
  }

  if (features.resolutionHits > 0) {
    reasons.push("resolution/source naming indicates released movie package");
    return ["video_movie", 0.87, reasons];
  }

  reasons.push("fallback video rule");
  return ["video_movie", 0.78, reasons];
}

function classifyDiskImage(record: TorrentRecord, features: TorrentFeatures): { kind: string; subtype: string; confidence: number; reasons: string[] } | undefined {
  const isoCount = features.extCounter[".iso"] ?? 0;
  if (isoCount === 0) {
    return undefined;
  }
  if (isoCount > 1) {
    return undefined;
  }

  const hasMdsPair = (features.extCounter[".mds"] ?? 0) > 0 || (features.extCounter[".mdf"] ?? 0) > 0;
  const name = record.torrentName.toLowerCase();
  const imageAssets = extCount(features, IMAGE_EXTENSIONS);
  const hasCueOrLog = (features.extCounter[".cue"] ?? 0) > 0 || (features.extCounter[".log"] ?? 0) > 0;

  if (DVD_ISO_HINT_RE.test(name) || hasMdsPair) {
    return {
      kind: "video",
      subtype: "video_dvd_iso",
      confidence: 0.9,
      reasons: ["ISO + DVD markers (name or MDS companion)"]
    };
  }

  if (MUSIC_DISC_HINT_RE.test(name) || hasCueOrLog || (imageAssets >= 3 && features.totalFiles > 1)) {
    return {
      kind: "music",
      subtype: "music_disc_image",
      confidence: 0.82,
      reasons: ["ISO package matches music-disc pattern (disc keyword or booklet assets)"]
    };
  }

  if (SOFTWARE_ISO_HINT_RE.test(name)) {
    return {
      kind: "software",
      subtype: "software_disk_image",
      confidence: 0.75,
      reasons: ["ISO package with software/game style naming"]
    };
  }

  return {
    kind: "software",
    subtype: "software_disk_image",
    confidence: 0.62,
    reasons: ["fallback ISO rule: classified as software disk image"]
  };
}

function classifyMusic(record: TorrentRecord): [string, number, string[]] {
  const audioExts: string[] = [];
  let hasCue = false;
  let hasRedundant = false;
  let hasLog = false;
  let hasValidTxt = false;
  let isVinyl = false;
  const baseToExts: Record<string, Set<string>> = {};

  for (const torrentFile of record.fileList) {
    const ext = extensionFromPath(torrentFile.path);
    const name = fileNameFromPath(torrentFile.path).toLowerCase();
    const base = ext ? name.slice(0, name.length - ext.length) : name;

    if (MUSIC_EXTENSIONS.has(ext)) {
      audioExts.push(ext);
      baseToExts[base] = baseToExts[base] ?? new Set<string>();
      baseToExts[base].add(ext);
      if (baseToExts[base].size > 1) {
        hasRedundant = true;
      }
    }

    if (ext === ".log" || ext === ".accurip") {
      hasLog = true;
    } else if (ext === ".txt") {
      if (VINYL_HINT_RE.test(base)) {
        isVinyl = true;
      }
      if (!EXCLUDE_MUSIC_TXT_RE.test(base) && torrentFile.size > 1024 && !DR_RE.test(base)) {
        hasValidTxt = true;
      }
    }

    if (ext === ".cue") {
      hasCue = true;
    }
  }

  if (audioExts.length === 1 && [".mp3", ".flac", ".m4a"].includes(audioExts[0])) {
    if (audioExts[0] === ".flac") {
      return ["music_single_track_flac", 0.95, ["single FLAC track package"]];
    }
    if (audioExts[0] === ".m4a") {
      return ["music_single_track_m4a", 0.93, ["single M4A track package"]];
    }
    return ["music_single_track_lossy", 0.92, ["single lossy track package"]];
  }

  if (hasRedundant) {
    return ["music_redundant_format", 0.91, ["same base track with multiple formats"]];
  }

  if (audioExts.some((ext) => UNCOMMON_MUSIC_EXTENSIONS.has(ext) || ext === ".iso")) {
    return ["music_uncommon_format", 0.9, ["detected uncommon high-end format"]];
  }

  if (audioExts.some((ext) => [".ogg", ".wma", ".ape"].includes(ext))) {
    return ["music_bad_format", 0.88, ["detected lower priority lossy/non-standard format"]];
  }

  if (audioExts.includes(".wav") && hasCue) {
    return ["music_full_album", 0.92, ["WAV + CUE full-disc pattern"]];
  }

  if (audioExts.length > 0 && audioExts.every((ext) => ext === ".flac") && !isVinyl) {
    if (hasLog) {
      return ["music_flac_with_log", 0.97, ["FLAC set with log/accurip proof"]];
    }
    if (hasValidTxt) {
      return ["music_flac_suspected_log", 0.86, ["FLAC set with valid info txt but missing log"]];
    }
    return ["music_flac_no_log", 0.81, ["FLAC set without log file"]];
  }

  if (audioExts.length > 0 && audioExts.every((ext) => ext === ".mp3")) {
    return ["music_mp3_lossy", 0.85, ["pure MP3 package"]];
  }

  if (audioExts.length > 0 && audioExts.every((ext) => ext === ".m4a")) {
    return ["music_m4a_lossy", 0.85, ["pure M4A package"]];
  }

  if (isVinyl) {
    return ["music_vinyl", 0.82, ["vinyl/lineage marker in metadata text"]];
  }

  return ["music_mixed", 0.74, ["mixed music package with no stronger subtype signal"]];
}

function extractFeatures(record: TorrentRecord): TorrentFeatures {
  const extCounter: Record<string, number> = {};
  let totalSize = 0;
  let largestFileSize = 0;

  for (const torrentFile of record.fileList) {
    totalSize += torrentFile.size;
    if (torrentFile.size > largestFileSize) {
      largestFileSize = torrentFile.size;
    }

    const ext = extensionFromPath(torrentFile.path);
    if (!ext) {
      continue;
    }
    extCounter[ext] = (extCounter[ext] ?? 0) + 1;
  }

  const textBlobs = [record.torrentName, ...record.fileList.map((item) => item.path)];

  return {
    totalFiles: record.fileList.length,
    totalSize,
    extCounter,
    largestFileSize,
    dominantExtension: dominantExtension(extCounter),
    seasonEpisodeHits: totalRegexHits(textBlobs, SEASON_EPISODE_RE),
    seasonHits: totalRegexHits(textBlobs, SEASON_RE),
    volumeHits: totalRegexHits(textBlobs, VOLUME_RE),
    blurayHits: totalRegexHits(textBlobs, BLURAY_RE),
    resolutionHits: totalRegexHits(textBlobs, RESOLUTION_RE),
    adultHits: totalRegexHits(textBlobs, ADULT_HINT_RE) + (ADULT_CODE_RE.test(record.torrentName) ? 1 : 0),
    videoFileCount: [...VIDEO_EXTENSIONS].reduce((acc, ext) => acc + (extCounter[ext] ?? 0), 0)
  };
}

function evaluateRules(record: TorrentRecord, features: TorrentFeatures, rules: Rule[]): RuleHit[] {
  const hits: RuleHit[] = [];

  for (const rule of rules) {
    if (!evaluateConditionTree(rule.when, record, features)) {
      continue;
    }

    if (rule.guards && evaluateConditionTree(rule.guards, record, features)) {
      continue;
    }

    hits.push({
      ruleId: rule.id,
      priority: rule.priority,
      confidence: rule.then.confidence,
      kind: rule.then.kind,
      subtype: rule.then.subtype,
      reason: rule.then.reason,
      specificity: specificity(rule.when)
    });
  }

  return hits;
}

function decideBest(hits: RuleHit[]): RuleHit | undefined {
  if (hits.length === 0) {
    return undefined;
  }

  return [...hits].sort((a, b) => {
    if (a.priority !== b.priority) {
      return b.priority - a.priority;
    }
    if (a.confidence !== b.confidence) {
      return b.confidence - a.confidence;
    }
    return b.specificity - a.specificity;
  })[0];
}

function evaluateConditionTree(node: ConditionNode, record: TorrentRecord, features: TorrentFeatures): boolean {
  if (Array.isArray(node.all)) {
    return node.all.every((item) => evaluateConditionTree(item, record, features));
  }

  if (Array.isArray(node.any)) {
    return node.any.some((item) => evaluateConditionTree(item, record, features));
  }

  if (Array.isArray(node.not)) {
    return !node.not.some((item) => evaluateConditionTree(item, record, features));
  }

  return evaluateLeaf(node, record, features);
}

function evaluateLeaf(node: ConditionNode, record: TorrentRecord, features: TorrentFeatures): boolean {
  if (Array.isArray(node.ext_any)) {
    return node.ext_any.some((ext) => (features.extCounter[ext] ?? 0) > 0);
  }

  if (Array.isArray(node.ext_all)) {
    return node.ext_all.every((ext) => (features.extCounter[ext] ?? 0) > 0);
  }

  if (typeof node.name_regex === "string") {
    return new RegExp(node.name_regex, "i").test(record.torrentName);
  }

  if (typeof node.total_files_gte === "number") {
    return features.totalFiles >= node.total_files_gte;
  }

  if (typeof node.total_files_lte === "number") {
    return features.totalFiles <= node.total_files_lte;
  }

  if (typeof node.size_gte === "number") {
    return features.totalSize >= node.size_gte;
  }

  if (isObject(node.feature_gte)) {
    return Object.entries(node.feature_gte).every(([key, value]) => {
      const featureValue = featureByRuleKey(features, key);
      return typeof featureValue === "number" && featureValue >= Number(value);
    });
  }

  if (isObject(node.feature_eq)) {
    return Object.entries(node.feature_eq).every(([key, value]) => featureByRuleKey(features, key) === value);
  }

  if (isObject(node.ext_count_gte)) {
    return Object.entries(node.ext_count_gte).every(([ext, value]) => {
      return (features.extCounter[ext] ?? 0) >= Number(value);
    });
  }

  if (Array.isArray(node.dominant_extension_in)) {
    return node.dominant_extension_in.includes(features.dominantExtension);
  }

  const unknownKeys = Object.keys(node).filter((key) => key !== "all" && key !== "any" && key !== "not" && !OPERATOR_KEYS.has(key));
  return unknownKeys.length === 0;
}

function specificity(node: ConditionNode): number {
  if (Array.isArray(node.all)) {
    return 1 + node.all.reduce((acc, item) => acc + specificity(item), 0);
  }

  if (Array.isArray(node.any)) {
    return 1 + node.any.reduce((acc, item) => acc + specificity(item), 0);
  }

  if (Array.isArray(node.not)) {
    return 1 + node.not.reduce((acc, item) => acc + specificity(item), 0);
  }

  return Object.keys(node).length;
}

function extCount(features: TorrentFeatures, extensions: Set<string>): number {
  let count = 0;
  for (const ext of extensions) {
    count += features.extCounter[ext] ?? 0;
  }
  return count;
}

function buildIndicators(features: TorrentFeatures, matchedRuleIds: string[]): Record<string, number | string | string[]> {
  return {
    total_files: features.totalFiles,
    total_size: features.totalSize,
    dominant_extension: features.dominantExtension,
    season_episode_hits: features.seasonEpisodeHits,
    season_hits: features.seasonHits,
    volume_hits: features.volumeHits,
    bluray_hits: features.blurayHits,
    adult_hits: features.adultHits,
    video_file_count: features.videoFileCount,
    matched_rule_ids: matchedRuleIds
  };
}

function featureByRuleKey(features: TorrentFeatures, key: string): number | string | undefined {
  switch (key) {
    case "total_files":
      return features.totalFiles;
    case "total_size":
      return features.totalSize;
    case "largest_file_size":
      return features.largestFileSize;
    case "dominant_extension":
      return features.dominantExtension;
    case "season_episode_hits":
      return features.seasonEpisodeHits;
    case "season_hits":
      return features.seasonHits;
    case "volume_hits":
      return features.volumeHits;
    case "bluray_hits":
      return features.blurayHits;
    case "resolution_hits":
      return features.resolutionHits;
    case "adult_hits":
      return features.adultHits;
    case "video_file_count":
      return features.videoFileCount;
    default:
      return undefined;
  }
}

function extensionFromPath(path: string): string {
  const normalized = path.replace(/\\/g, "/").toLowerCase();
  const slashIndex = normalized.lastIndexOf("/");
  const name = slashIndex >= 0 ? normalized.slice(slashIndex + 1) : normalized;
  const dotIndex = name.lastIndexOf(".");
  if (dotIndex <= 0 || dotIndex === name.length - 1) {
    return "";
  }
  return name.slice(dotIndex);
}

function fileNameFromPath(path: string): string {
  const normalized = path.replace(/\\/g, "/");
  const slashIndex = normalized.lastIndexOf("/");
  return slashIndex >= 0 ? normalized.slice(slashIndex + 1) : normalized;
}

function dominantExtension(extCounter: Record<string, number>): string {
  let topExt = "";
  let topCount = 0;

  for (const [ext, count] of Object.entries(extCounter)) {
    if (count > topCount) {
      topCount = count;
      topExt = ext;
    }
  }
  return topExt;
}

function totalRegexHits(values: string[], regex: RegExp): number {
  return values.reduce((acc, value) => {
    const matcher = new RegExp(regex.source, regex.flags);
    const matches = value.match(matcher);
    return acc + (matches ? matches.length : 0);
  }, 0);
}

function clamp(value: number): number {
  return Math.max(0, Math.min(1, value));
}

function createTraceId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

function asString(value: unknown, context: string): string {
  if (typeof value !== "string" || value.length === 0) {
    throw new Error(`${context} must be a non-empty string.`);
  }
  return value;
}

function asNumber(value: unknown, context: string): number {
  if (typeof value !== "number" || Number.isNaN(value)) {
    throw new Error(`${context} must be a number.`);
  }
  return value;
}

function asBoolean(value: unknown, context: string): boolean {
  if (typeof value !== "boolean") {
    throw new Error(`${context} must be a boolean.`);
  }
  return value;
}

function asThen(value: unknown, context: string) {
  if (!isObject(value)) {
    throw new Error(`${context} must be an object.`);
  }
  return {
    kind: asString(value.kind, `${context}.kind`),
    subtype: asString(value.subtype, `${context}.subtype`),
    confidence: asNumber(value.confidence, `${context}.confidence`),
    reason: asString(value.reason, `${context}.reason`)
  };
}

function asCondition(value: unknown, context: string): ConditionNode {
  if (!isObject(value)) {
    throw new Error(`${context} must be an object.`);
  }
  return value as ConditionNode;
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
