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

export type ChannelConfig = {
  enabled: boolean;
  push_card: boolean;
  push_pdf: boolean;
  push_mindmap: boolean;
};

export type JobConfigType = {
  enable_summary: boolean;
  enable_actions: boolean;
  enable_insights: boolean;
  enable_report_render: boolean;
  enable_mindmap: boolean;
  enable_delivery: boolean;
  enable_task_sync: boolean;
  feishu: ChannelConfig;
  jira: ChannelConfig;
};

export type AgentEvent = {
  type: string;
  message: string;
  progress?: number;
};

export type SystemConfig = {
  llm_provider: string;
  llm_api_key: string;
  llm_model: string;
  llm_base_url: string;
  asr_engine: string;
  whisper_device: string;
  whisper_model_size: string;
  whisper_language: string;
  hf_token: string;
  asr_api_key: string;
  asr_base_url: string;
  asr_model: string;
  noteking_proxy: string;
  bilibili_sessdata: string;
  feishu_app_id: string;
  feishu_app_secret: string;
  feishu_receive_id: string;
  feishu_webhook_url: string;
  jira_server: string;
  jira_email: string;
  jira_api_token: string;
  jira_project_key: string;
  port: string;
  log_level: string;
};

export type ReportListItem = {
  meeting_id: string;
  title: string;
  status: string;
  duration: number;
  num_speakers: number;
  created_at: number;
};

export type TranscriptSegment = {
  start: number;
  end: number;
  text: string;
  speaker?: string;
};

export type SpeakerStat = {
  speaker: string;
  duration: number;
  percentage: number;
};
