export type OutputFiles = Record<string, string>;

export type Result = {
  meeting_id?: string;
  title: string;
  content: string;
  source: string;
  duration: number;
  num_speakers?: number;
  speakers?: string[];
  output_files?: OutputFiles;
  summary?: any;
  actions?: any;
  insights?: any;
  diarized_transcript?: string;
};

export type HistoryItem = Result & {
  id: string;
  input: string;
  timestamp: number;
  contentPreview: string;
};

export type InputMode = "url" | "file";

export type JobConfigType = {
  enable_summary: boolean;
  enable_actions: boolean;
  enable_insights: boolean;
  enable_feishu: boolean;
  enable_jira: boolean;
  feishu_app_id: string;
  feishu_app_secret: string;
  feishu_webhook_url: string;
  jira_server: string;
  jira_email: string;
  jira_api_token: string;
};
