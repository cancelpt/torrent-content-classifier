import bencode from "bencode";
import { Buffer } from "buffer";
import type { TorrentFileRecord, TorrentRecord } from "./types";

if (!(globalThis as { Buffer?: typeof Buffer }).Buffer) {
  (globalThis as { Buffer: typeof Buffer }).Buffer = Buffer;
}

const textDecoder = new TextDecoder("utf-8");

export async function parseTorrentFile(file: File): Promise<TorrentRecord> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  const decoded = bencode.decode(bytes);
  const root = asMap(decoded, "torrent root");
  const info = getRequired(root, "info");
  const infoMap = asMap(info, "info");
  const torrentName = toText(getRequired(infoMap, "name"));
  const fileList = parseFileList(infoMap, torrentName);
  const infoHash = await computeInfoHash(info);

  return {
    infoHash,
    torrentName,
    fileList
  };
}

function parseFileList(info: unknown, torrentName: string): TorrentFileRecord[] {
  const infoMap = asMap(info, "info");
  const filesValue = getOptional(infoMap, "files");

  if (Array.isArray(filesValue)) {
    return filesValue.map((item, index) => {
      const itemMap = asMap(item, `files[${index}]`);
      const rawLength = getRequired(itemMap, "length");
      const rawPath = getRequired(itemMap, "path");
      const size = toNumber(rawLength);
      const pathSegments = asArray(rawPath, `files[${index}].path`).map((value) => toText(value));
      return {
        path: pathSegments.join("/"),
        size
      };
    });
  }

  const lengthValue = getOptional(infoMap, "length");
  if (lengthValue === undefined) {
    return [];
  }

  return [
    {
      path: torrentName,
      size: toNumber(lengthValue)
    }
  ];
}

async function computeInfoHash(info: unknown): Promise<string> {
  const encodedInfo = asBytes(bencode.encode(info));
  const digest = await crypto.subtle.digest("SHA-1", encodedInfo);
  return Array.from(new Uint8Array(digest))
    .map((item) => item.toString(16).padStart(2, "0"))
    .join("");
}

function asMap(value: unknown, context: string): Record<string, unknown> {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  throw new Error(`${context} should be an object.`);
}

function asArray(value: unknown, context: string): unknown[] {
  if (!Array.isArray(value)) {
    throw new Error(`${context} should be an array.`);
  }
  return value;
}

function getRequired(map: Record<string, unknown>, key: string): unknown {
  const found = getOptional(map, key);
  if (found === undefined) {
    throw new Error(`Missing required key "${key}" in torrent metadata.`);
  }
  return found;
}

function getOptional(map: Record<string, unknown>, key: string): unknown {
  if (key in map) {
    return map[key];
  }

  for (const [entryKey, value] of Object.entries(map)) {
    if (entryKey === key) {
      return value;
    }
  }
  return undefined;
}

function toText(value: unknown): string {
  if (typeof value === "string") {
    return value;
  }
  if (Buffer.isBuffer(value)) {
    return value.toString("utf-8");
  }
  if (value instanceof Uint8Array) {
    return textDecoder.decode(value);
  }
  if (typeof value === "number" || typeof value === "bigint") {
    return String(value);
  }
  throw new Error("Could not decode torrent text field.");
}

function toNumber(value: unknown): number {
  if (typeof value === "number") {
    return value;
  }
  if (typeof value === "bigint") {
    return Number(value);
  }
  if (Buffer.isBuffer(value)) {
    const asText = value.toString("utf-8");
    const parsed = Number(asText);
    if (!Number.isNaN(parsed)) {
      return parsed;
    }
  }
  throw new Error("Could not decode torrent numeric field.");
}

function asBytes(value: unknown): Uint8Array {
  if (value instanceof Uint8Array) {
    return value;
  }
  if (Buffer.isBuffer(value)) {
    return new Uint8Array(value);
  }
  throw new Error("Unable to encode bytes.");
}
