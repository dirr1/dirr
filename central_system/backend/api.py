from fastapi import FastAPI, BackgroundTasks
from typing import List, Dict, Any
from central_system.backend.analysis import AnalysisEngine
from central_system.backend.monitor import MonitorEngine
from central_system.backend.alerts import AlertManager
import asyncio

app = FastAPI(title="Polymarket Central Intelligence Dashboard API")

# Global instances
analysis_engine = AnalysisEngine()
alert_manager = AlertManager()
monitor_engine = MonitorEngine(analysis_engine, alert_manager)

@app.on_event("startup")
async def startup_event():
    # Start the monitor in the background
    asyncio.create_task(monitor_engine.start_polling())

@app.on_event("shutdown")
async def shutdown_event():
    await monitor_engine.stop()

@app.get("/health")
def health():
    return {"status": "running"}

@app.get("/stats")
def get_stats():
    return {
        "total_trades_analyzed": len(monitor_engine.processed_trades),
        "unique_wallets_tracked": len(monitor_engine.wallets),
        "markets_cached": len(monitor_engine.market_cache)
    }

@app.get("/whales")
def get_whales(min_volume: float = 10000):
    whales = []
    for addr, data in monitor_engine.wallets.items():
        if data['total_volume'] >= min_volume:
            whales.append({
                "address": addr,
                "total_volume": data['total_volume'],
                "trade_count": len(data['trades'])
            })
    return sorted(whales, key=lambda x: x['total_volume'], reverse=True)

@app.get("/suspicious-wallets")
def get_suspicious():
    suspicious = []
    for addr, data in monitor_engine.wallets.items():
        if len(data['trades']) >= 3:
            # Pass market info if available
            analysis = analysis_engine.analyze_wallet(addr, data['trades'], monitor_engine.market_cache)
            if analysis.get('suspicion_level') != 'low':
                suspicious.append(analysis)
    return sorted(suspicious, key=lambda x: x.get('p_value', 1))

@app.post("/trigger-manual-analysis/{wallet_address}")
async def trigger_analysis(wallet_address: str, background_tasks: BackgroundTasks):
    if wallet_address not in monitor_engine.wallets:
        return {"error": "Wallet not found"}

    wallet_data = monitor_engine.wallets[wallet_address]
    alert_data = {
        "wallet_address": wallet_address,
        "market_question": "Manual Review",
        "value_usd": wallet_data['total_volume'],
        "timestamp": wallet_data['trades'][-1]['timestamp'] if wallet_data['trades'] else 0
    }

    background_tasks.add_task(alert_manager.broadcast_alert, alert_data)
    return {"status": "Analysis queued"}
