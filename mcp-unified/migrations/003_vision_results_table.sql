-- Migration 003: Create vision_results table for hybrid storage
-- Purpose: Store high-confidence vision/OCR results with structured schema
-- Created: 2026-03-03
-- Author: AI Assistant

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Main table for vision processing results
CREATE TABLE IF NOT EXISTS vision_results (
    -- Primary identification
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    processing_id UUID DEFAULT gen_random_uuid() NOT NULL,
    
    -- File information
    file_name TEXT NOT NULL,
    file_path TEXT,
    file_hash VARCHAR(64),
    file_size_bytes BIGINT,
    mime_type VARCHAR(100),
    
    -- Processing metadata
    namespace TEXT NOT NULL DEFAULT 'default',
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    processing_time_ms INTEGER CHECK (processing_time_ms >= 0),
    
    -- Vision/OCR results
    extracted_text TEXT,
    confidence_score DECIMAL(4,3) CHECK (confidence_score >= 0 AND confidence_score <= 1),
    confidence_threshold DECIMAL(4,3) DEFAULT 0.8 CHECK (confidence_threshold >= 0 AND confidence_threshold <= 1),
    processing_method VARCHAR(50) CHECK (processing_method IN ('vision', 'ocr', 'hybrid', 'manual')),
    model_used VARCHAR(100),
    
    -- Content classification
    document_type VARCHAR(50),
    status VARCHAR(20) DEFAULT 'success' CHECK (status IN ('success', 'failed', 'low_confidence', 'pending_review', 'verified')),
    
    -- Structured data (JSONB for flexibility)
    extracted_entities JSONB DEFAULT '{}',
    processing_metadata JSONB DEFAULT '{}',
    
    -- LTM linking (optional reference to memories table)
    ltm_key TEXT,
    
    -- Audit trail
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_by VARCHAR(100),
    tenant_id VARCHAR(50) DEFAULT 'default'
);

-- Create indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_vision_confidence ON vision_results(confidence_score DESC);
CREATE INDEX IF NOT EXISTS idx_vision_processed_at ON vision_results(processed_at DESC);
CREATE INDEX IF NOT EXISTS idx_vision_document_type ON vision_results(document_type);
CREATE INDEX IF NOT EXISTS idx_vision_status ON vision_results(status);
CREATE INDEX IF NOT EXISTS idx_vision_namespace ON vision_results(namespace);
CREATE INDEX IF NOT EXISTS idx_vision_file_hash ON vision_results(file_hash);
CREATE INDEX IF NOT EXISTS idx_vision_tenant ON vision_results(tenant_id);
CREATE INDEX IF NOT EXISTS idx_vision_processing_method ON vision_results(processing_method);

-- Composite index for common filtered queries
CREATE INDEX IF NOT EXISTS idx_vision_namespace_confidence ON vision_results(namespace, confidence_score DESC);
CREATE INDEX IF NOT EXISTS idx_vision_status_processed_at ON vision_results(status, processed_at DESC);

-- GIN index for JSONB columns (efficient for JSON queries)
CREATE INDEX IF NOT EXISTS idx_vision_entities_gin ON vision_results USING GIN (extracted_entities);
CREATE INDEX IF NOT EXISTS idx_vision_metadata_gin ON vision_results USING GIN (processing_metadata);

-- Comments for documentation
COMMENT ON TABLE vision_results IS 'Stores vision/OCR processing results with confidence scores for hybrid LTM+SQL storage';
COMMENT ON COLUMN vision_results.confidence_score IS 'Confidence score from 0.000 to 1.000';
COMMENT ON COLUMN vision_results.processing_method IS 'Method used: vision, ocr, hybrid, or manual';
COMMENT ON COLUMN vision_results.status IS 'Processing status: success, failed, low_confidence, pending_review, verified';
COMMENT ON COLUMN vision_results.ltm_key IS 'Reference key to long-term memory (memories table)';

-- Create a view for high-confidence results only (convenience)
CREATE OR REPLACE VIEW vision_results_high_confidence AS
SELECT *
FROM vision_results
WHERE confidence_score >= 0.8
  AND status IN ('success', 'verified')
ORDER BY confidence_score DESC, processed_at DESC;

-- Create a view for analytics/reporting
CREATE OR REPLACE VIEW vision_processing_stats AS
SELECT 
    DATE(processed_at) as processing_date,
    namespace,
    processing_method,
    document_type,
    status,
    COUNT(*) as result_count,
    AVG(confidence_score) as avg_confidence,
    MIN(confidence_score) as min_confidence,
    MAX(confidence_score) as max_confidence,
    AVG(processing_time_ms) as avg_processing_time_ms
FROM vision_results
GROUP BY DATE(processed_at), namespace, processing_method, document_type, status;

-- Function to update updated_at timestamp automatically
CREATE OR REPLACE FUNCTION update_vision_results_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for automatic updated_at
DROP TRIGGER IF EXISTS trigger_vision_results_updated_at ON vision_results;
CREATE TRIGGER trigger_vision_results_updated_at
    BEFORE UPDATE ON vision_results
    FOR EACH ROW
    EXECUTE FUNCTION update_vision_results_updated_at();

-- Insert sample data for testing (optional, comment out in production)
-- INSERT INTO vision_results (file_name, confidence_score, processing_method, document_type, status, extracted_text)
-- VALUES ('sample_invoice.pdf', 0.92, 'hybrid', 'invoice', 'verified', 'Sample invoice text...');

-- Grant permissions (adjust as needed)
-- GRANT SELECT, INSERT, UPDATE ON vision_results TO mcp_user;
-- GRANT USAGE, SELECT ON SEQUENCE vision_results_id_seq TO mcp_user;

COMMIT;

-- Verification query
SELECT 
    'vision_results table created successfully' as message,
    COUNT(*) as index_count
FROM pg_indexes 
WHERE tablename = 'vision_results';
