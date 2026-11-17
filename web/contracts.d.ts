interface AthleteSummary { id: string; name: string; focus: string }
interface Goal { goal_type: string; goal_date: string; target_time_min: number | null; secondary: string }
interface StrengthFields { exercise?: string | null; muscle_group?: string | null; sets?: number | null; reps?: number | null; load_kg?: number | null; rir?: number | null }
interface Observation extends StrengthFields {
  athlete_id: string; date: string; timestamp: string; timezone: string; sport_type: string;
  duration_min: number; session_rpe: number; distance_km: number | null;
  sleep_hours: number | null; fatigue: number | null; soreness: number | null; stress: number | null;
  hrv_ms: number | null; resting_hr_bpm: number | null; source: string; recovery_source?: string;
  hrv_device?: string | null; hrv_protocol?: string | null;
  resting_hr_device?: string | null; resting_hr_protocol?: string | null;
}
interface Session extends StrengthFields { date: string; title: string; sport_type: string; duration_min: number; session_rpe: number; key: boolean }
interface Recommendation { title: string; sport_type: string; duration_min: number; session_rpe: number; load_au: number; adjusted: boolean; explanation: string; rule_version?: string; evidence_status?: string }
type Mode = "BUILD" | "MAINTAIN" | "RECOVER" | "PROTECT" | "INSUFFICIENT";
interface EvidenceSource { id: string; citation: string; title: string; url: string; accessible_url?: string; published_on?: string; reviewed_on?: string; doi?: string; correction_url?: string; type: string; population: string; protocol: string; supports: string; limitations: string; verification: string }
interface EvidenceRule { id: string; title: string; version: string; kind: string; parameters: Record<string, number | string>; source_ids: string[]; evidence: { variable: string; method: string; exact_threshold: string }; population: string; protocol: string; limitations: string }
interface EvidenceManifest { rule_version: string; reviewed_on: string; rules: EvidenceRule[]; sources: EvidenceSource[]; scope: string }
interface RuleTrace { rule_version: string; rules: EvidenceRule[]; sources: EvidenceSource[]; threshold_status: string; confidence: null; message: string }
interface BaselineQuality { unit: string; window_days: number; window_start: string; window_end: string; observation_count: number; used_count: number; required_count: number; mean: number | null; population_sd: number | null; coefficient_of_variation_pct: number | null; status: string; comparability: string; unknown_metadata_count: number; excluded_mismatch_count: number; current_device: string | null; current_protocol: string | null; notes: string[]; rule_id: string }
interface LoadBaselineQuality { observation_count: number; required_count: number; mean_daily_load_au: number | null; population_sd_daily_au: number | null; weekly_average_au: number | null; coefficient_of_variation_pct: number | null; status: string; comparability: string }
interface ObservedSignal { rule_id: string; value: number | null; unit: string; operator: string; threshold: number; crossed: boolean | null; threshold_status: string; comparability: string }
interface MonitoringReview {
  rule_id: string; status: string; summary: string; combined_signal_rule_ids: string[]; missing_rule_ids: string[];
  facts: { weekly_load_au: number | null; baseline_weekly_load_au: number | null; week_days_observed: number; baseline_days_observed: number; recovery_source: string };
  contexts: { rule_id: string; source_ids: string[]; support: string; comparability: string }[];
  criterion: string; review_action: string; limitations: string;
}
interface Prediction { contract_version: number; prediction_source: string; readiness_score: number | null; fatigue_index: number | null; mode: Mode; overload_pattern: string; signals: string[]; reasons: string[]; component_scores: Record<string, number>; limitations: string; rule_version: string; observed_signals: ObservedSignal[]; evidence_status: string; trace: RuleTrace; monitoring_review: MonitoringReview }
interface Features {
  contract_version: number; as_of: string; current: Partial<Observation> | null;
  weekly_load_au: number | null; observed_week_load_au: number; week_days_observed: number; baseline_weekly_load_au: number | null;
  load_change_pct: number | null; monotony_ratio: number | null; strain_au: number | null;
  hrv_baseline_ms: number | null; resting_hr_baseline_bpm: number | null; hrv_change_pct: number | null; hr_reserve_ratio: number | null;
  strength_volume_kg: number | null; strength_change_pct: number | null; direct_sets_by_muscle: Record<string, number> | null;
  e1rm_estimates: { exercise: string; date: string; e1rm_kg: number; protocol_status: string; evidence_status: string; limitations: string }[];
  pace_min_per_km: number | null; pace_change_pct: number | null;
  pace_quality: { recent_run_count: number; baseline_run_count: number; comparability: string; status: string };
  baseline_quality: { hrv: BaselineQuality; resting_hr: BaselineQuality; weekly_load: LoadBaselineQuality };
  history: { date: string; load_au: number | null; source: string }[]; warnings: string[];
}
interface Win { id: string; title: string; category: string; reason: string; date: string; goal_type: string; rule_version?: string; trace_status: string; evidence_status?: string }
interface Completion { date: string; duration_min: number; session_rpe: number; adapted: boolean; within_dose: boolean; on_plan: boolean; mode_at_completion: Mode; key: boolean; decision_id: string | null; trace_status: string; rule_version?: string | null }
interface DecisionSummary { id: string; as_of: string; trigger: string; captured_at: string; rule_version: string; mode: Mode; recommendation: Recommendation; input_digest: string }
interface DecisionOutcome extends Completion { recorded_at: string; actual_load_au: number; actual_distance_km: number | null; actual_strength_volume_kg: number | null; chosen_dose: Recommendation; limitations: string }
interface Athlete extends AthleteSummary { timezone: string; goal: Goal; records: Observation[]; plan: Session[]; wins: Win[]; completions: Completion[]; adjustments: Record<string, { recommendation: Recommendation; mode: Mode; signals: string[]; accepted_at: string; decision_id: string | null; trace_status: string; rule_version?: string }>; checkins: Record<string, Partial<Observation>>; decision_snapshots: DecisionSummary[]; decision_outcomes: DecisionOutcome[] }
interface View { athlete: Athlete; features: Features; prediction: Prediction; today_session: Session; recommendation: Recommendation; today: string; adherence_pct: number | null; goal_days_remaining: number; scheduled_today: boolean; evidence: EvidenceManifest }
interface CoachReply { answer: string; source: string; as_of: string; disclaimer: string; trace: RuleTrace; baseline_quality: Features["baseline_quality"]; monitoring_review: MonitoringReview }
