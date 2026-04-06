-- Autonomous Social Media Growth Agent — Database Schema
-- MySQL 8.0

CREATE DATABASE IF NOT EXISTS social_agent CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE social_agent;

-- Users
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(36) PRIMARY KEY DEFAULT (UUID()),
    name VARCHAR(255) NOT NULL,
    linkedin_url VARCHAR(500),
    twitter_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Profile Intelligence Reports
CREATE TABLE IF NOT EXISTS profile_reports (
    id VARCHAR(36) PRIMARY KEY DEFAULT (UUID()),
    user_id VARCHAR(36) NOT NULL,
    report_json LONGTEXT NOT NULL,  -- Full structured report as JSON
    status ENUM('pending','complete','failed') DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Competitor Analysis Reports
CREATE TABLE IF NOT EXISTS competitor_reports (
    id VARCHAR(36) PRIMARY KEY DEFAULT (UUID()),
    user_id VARCHAR(36) NOT NULL,
    report_json LONGTEXT NOT NULL,
    status ENUM('pending','complete','failed') DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Content Calendars
CREATE TABLE IF NOT EXISTS content_calendars (
    id VARCHAR(36) PRIMARY KEY DEFAULT (UUID()),
    user_id VARCHAR(36) NOT NULL,
    title VARCHAR(255) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    calendar_json LONGTEXT NOT NULL,  -- Full calendar entries as JSON
    status ENUM('draft','under_review','approved','locked') DEFAULT 'draft',
    review_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Individual Calendar Entries
CREATE TABLE IF NOT EXISTS calendar_entries (
    id VARCHAR(36) PRIMARY KEY DEFAULT (UUID()),
    calendar_id VARCHAR(36) NOT NULL,
    day_number INT NOT NULL,
    scheduled_date DATE NOT NULL,
    platform ENUM('linkedin','twitter','both') NOT NULL,
    topic VARCHAR(500) NOT NULL,
    format VARCHAR(100),      -- e.g. 'short_post','thread','article','carousel'
    posting_time TIME,
    status ENUM('planned','content_generated','approved','published','failed') DEFAULT 'planned',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (calendar_id) REFERENCES content_calendars(id) ON DELETE CASCADE
);

-- Generated Posts
CREATE TABLE IF NOT EXISTS posts (
    id VARCHAR(36) PRIMARY KEY DEFAULT (UUID()),
    entry_id VARCHAR(36) NOT NULL,
    body_copy LONGTEXT,
    hashtags TEXT,
    visual_prompt LONGTEXT,
    visual_url VARCHAR(500),      -- if actual image was generated
    copy_status ENUM('pending','approved','regenerate') DEFAULT 'pending',
    hashtag_status ENUM('pending','approved','regenerate') DEFAULT 'pending',
    visual_status ENUM('pending','approved','regenerate') DEFAULT 'pending',
    publish_status ENUM('draft','queued','posted','failed') DEFAULT 'draft',
    published_at TIMESTAMP NULL,
    platform_post_id VARCHAR(255),   -- ID returned by platform after publish
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (entry_id) REFERENCES calendar_entries(id) ON DELETE CASCADE
);

-- Pipeline Run Metrics (observability)
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id VARCHAR(36) PRIMARY KEY DEFAULT (UUID()),
    user_id VARCHAR(36) NOT NULL,
    stage VARCHAR(100) NOT NULL,     -- profile_agent, competitor_agent, etc.
    status ENUM('running','success','failed') DEFAULT 'running',
    token_usage INT DEFAULT 0,
    latency_ms INT DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Post Engagement Metrics (FR-7 bonus)
CREATE TABLE IF NOT EXISTS post_metrics (
    id VARCHAR(36) PRIMARY KEY DEFAULT (UUID()),
    post_id VARCHAR(36) NOT NULL,
    impressions INT DEFAULT 0,
    reactions INT DEFAULT 0,
    comments INT DEFAULT 0,
    shares INT DEFAULT 0,
    polled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE
);

-- HITL Conversation History
CREATE TABLE IF NOT EXISTS hitl_sessions (
    id VARCHAR(36) PRIMARY KEY DEFAULT (UUID()),
    user_id VARCHAR(36) NOT NULL,
    session_type ENUM('calendar_review','content_review') NOT NULL,
    reference_id VARCHAR(36) NOT NULL,   -- calendar_id or post_id
    messages_json LONGTEXT NOT NULL,     -- Chat history as JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
