import os
import asyncio
import time
import pytest
from unittest.mock import MagicMock, patch
from app.core.stores import CaseContext
from app.modules.dominion import Dominion
from app.models import EvidenceSegment, Modality, RunStatus

@pytest.mark.asyncio
async def test_maintenance_performance(tmp_path):
    case_id = "perf_test_case"
    ctx = CaseContext(case_id, base_storage_path=str(tmp_path))
    dominion = Dominion(ctx)

    # 1. Prepare 10 draft segments
    for i in range(10):
        seg = EvidenceSegment(
            segment_id=f"seg_{i}",
            source_asset_id="asset_1",
            modality=Modality.AUDIO_TRANSCRIPT,
            location=f"0-{i}",
            text=f"Draft text {i}",
            confidence=0.5,
            extraction_method="whisper-tiny",
            derived=False,
            metadata={"transcription_quality": "draft"}
        )
        ctx.ledger.append_segment(seg)

    # 2. Mock refine_transcription to take 0.1s
    def mock_refine(seg):
        time.sleep(0.1)
        seg.metadata["transcription_quality"] = "final"
        return seg

    with patch.object(dominion.conversion, "refine_transcription", side_effect=mock_refine):
        start_time = time.perf_counter()

        # Run maintenance
        run_state = await dominion.workflow_background_maintenance()

        # Wait for completion
        while True:
            await asyncio.sleep(0.05)
            status = dominion.get_job_status(run_state.run_id)
            if status.status in [RunStatus.COMPLETE, RunStatus.FAILED]:
                break

        end_time = time.perf_counter()
        duration = end_time - start_time
        print(f"\nMaintenance took {duration:.4f} seconds")

        assert status.status == RunStatus.COMPLETE
        assert status.result_payload["upgraded_segments"] == 10

if __name__ == "__main__":
    import sys
    import shutil

    # Simple manual run if not using pytest
    tmp_dir = "/tmp/legalmind_bench"
    if os.path.exists(tmp_dir):
        shutil.rmtree(tmp_dir)
    os.makedirs(tmp_dir)

    async def run():
        await test_maintenance_performance(tmp_dir)

    asyncio.run(run())
