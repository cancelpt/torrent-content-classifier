export interface TorrentFileRecord {
  path: string;
  size: number;
}

export interface TorrentRecord {
  infoHash: string;
  torrentName: string;
  fileList: TorrentFileRecord[];
}

export interface RuleThen {
  kind: string;
  subtype: string;
  confidence: number;
  reason: string;
}

export interface Rule {
  id: string;
  priority: number;
  enabled: boolean;
  when: ConditionNode;
  then: RuleThen;
  guards?: ConditionNode;
}

export type ConditionNode = {
  all?: ConditionNode[];
  any?: ConditionNode[];
  not?: ConditionNode[];
  ext_any?: string[];
  ext_all?: string[];
  name_regex?: string;
  total_files_gte?: number;
  total_files_lte?: number;
  size_gte?: number;
  feature_gte?: Record<string, number>;
  feature_eq?: Record<string, number | string | boolean>;
  ext_count_gte?: Record<string, number>;
  dominant_extension_in?: string[];
  [key: string]: unknown;
};

export interface ClassificationResult {
  infoHash: string;
  torrentName: string;
  kind: string;
  subtype: string;
  confidence: number;
  reasons: string[];
  matchedRuleIds: string[];
  traceId: string;
  indicators: Record<string, number | string | string[]>;
}
