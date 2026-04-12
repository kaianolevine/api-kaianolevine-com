ALTER TABLE pipeline_evaluations
  ADD CONSTRAINT pipeline_evaluations_severity_check
  CHECK (severity IN ('CRITICAL', 'ERROR', 'WARN', 'INFO', 'SUCCESS'))
  NOT VALID;
