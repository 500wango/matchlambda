"""Add system_settings and audit_logs tables

Revision ID: 0003_add_settings_and_audit_logs
Revises: 0002_add_user_is_admin
Create Date: 2026-10-04 03:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0003_add_settings_and_audit_logs'
down_revision: Union[str, None] = '0002_add_user_is_admin'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE IF NOT EXISTS system_settings (
        key VARCHAR(64) PRIMARY KEY,
        value JSONB NOT NULL,
        description TEXT,
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS audit_logs (
        id UUID PRIMARY KEY,
        admin_email VARCHAR(255) NOT NULL,
        action VARCHAR(64) NOT NULL,
        target VARCHAR(128),
        details JSONB,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs (created_at DESC);

    -- Seed initial system settings
    INSERT INTO system_settings (key, value, description)
    VALUES 
    ('quant_risk', '{"value_scanner_min_ev": 0.05, "kelly_fraction": 0.5, "max_stake_cap": 0.05, "dixon_coles_decay_xi": 0.0018, "min_training_matches": 60}'::jsonb, '全局量化模型超参数与凯利风控参数')
    ON CONFLICT (key) DO NOTHING;

    INSERT INTO system_settings (key, value, description)
    VALUES 
    ('data_provider', '{"the_odds_api_key": "", "sharp_bookmakers": ["pinnacle", "betfair_ex_uk", "bet365"], "polling_interval_hours": 4, "live_monitoring_enabled": true}'::jsonb, '实时行情源配置与轮询策略')
    ON CONFLICT (key) DO NOTHING;

    INSERT INTO system_settings (key, value, description)
    VALUES 
    ('monetization', '{"monthly_price_usd": 29.0, "season_price_usd": 149.0, "new_user_trial_days": 3, "accepted_tokens": ["USDTTRC20", "USDTERC20", "USDC", "BTC"]}'::jsonb, '会员订阅定价与拉新试用期策略')
    ON CONFLICT (key) DO NOTHING;

    INSERT INTO system_settings (key, value, description)
    VALUES 
    ('notifications', '{"telegram_enabled": false, "telegram_bot_token": "", "telegram_channel_id": "", "telegram_min_ev": 0.08, "webhook_url": "", "webhook_enabled": false}'::jsonb, 'Telegram Bot 与 Webhook 告警推送配置')
    ON CONFLICT (key) DO NOTHING;
    """)


def downgrade() -> None:
    op.execute("""
    DROP TABLE IF EXISTS audit_logs CASCADE;
    DROP TABLE IF EXISTS system_settings CASCADE;
    """)
