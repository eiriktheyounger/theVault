#!/usr/bin/env python3
"""
Batch RAG reindexing script - processes vault files in batches of 100-200 files.

Usage:
    python batch_reindex.py [--batch-size 150]
"""
import argparse
import os
import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from System.Scripts.RAG.retrieval.store import rebuild_chunks_from_vault, get_sqlite_rw
from System.Scripts.RAG.retrieval.indexer import reindex
from System.Scripts.RAG.config import VAULT_ROOT


SKIP_DIRS = {
    # Hidden / system
    '.git', '.obsidian', '.trash', '.vault_organizer', 'node_modules',
    # Noise / archives / staging
    '_Dupes', '_archive', 'TOCBak', 'Processed',
    # High-volume low-signal
    'TimeTracking',
    # System infra (not content)
    'System', 'Templates', 'Assets', 'attachments',
}


def get_all_markdown_files(vault_path: Path) -> list[str]:
    """Get all markdown files from the vault, excluding noise directories."""
    markdown_files = []

    for root, dirs, files in os.walk(vault_path):
        # Skip hidden dirs and excluded dirs
        dirs[:] = [d for d in dirs
                   if not d.startswith('.') and d not in SKIP_DIRS]

        for file in files:
            if file.endswith(('.md', '.markdown')):
                full_path = os.path.join(root, file)
                markdown_files.append(full_path)

    return sorted(markdown_files)


def process_batch(batch_num: int, batch_files: list[str], total_batches: int):
    """Process a single batch of files."""
    print(f"\n{'='*60}")
    print(f"Batch {batch_num}/{total_batches}: Processing {len(batch_files)} files...")
    print(f"{'='*60}")

    start_time = time.time()

    try:
        # Rebuild chunks for this batch
        result = rebuild_chunks_from_vault(paths=batch_files)

        # Show some sample files being processed
        print(f"Sample files:")
        for i, fpath in enumerate(batch_files[:5]):
            rel_path = os.path.relpath(fpath, VAULT_ROOT)
            print(f"  {i+1}. {rel_path}")
        if len(batch_files) > 5:
            print(f"  ... and {len(batch_files) - 5} more files")

        elapsed = time.time() - start_time
        print(f"\n✓ Batch {batch_num} completed in {elapsed:.1f}s")
        print(f"  Documents processed: {result.get('documents_processed', 0)}")
        print(f"  Chunks created: {result.get('chunks_created', 0)}")

        return True

    except Exception as e:
        print(f"\n✗ Error processing batch {batch_num}: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(description='Batch reindex the RAG vault')
    parser.add_argument('--batch-size', type=int, default=150,
                       help='Number of files to process per batch (default: 150)')
    parser.add_argument('--start-batch', type=int, default=1,
                       help='Start from batch N (default: 1)')
    args = parser.parse_args()

    print("="*60)
    print("RAG Batch Reindexing")
    print("="*60)
    print(f"Vault path: {VAULT_ROOT}")
    print(f"Batch size: {args.batch_size} files")
    print()

    # Get all markdown files
    print("Scanning vault for markdown files...")
    all_files = get_all_markdown_files(VAULT_ROOT)
    total_files = len(all_files)

    if total_files == 0:
        print("No markdown files found!")
        return 1

    print(f"Found {total_files:,} markdown files")

    # Calculate batches
    batch_size = args.batch_size
    total_batches = (total_files + batch_size - 1) // batch_size

    print(f"Will process in {total_batches} batches of ~{batch_size} files each")
    print()

    # Process each batch
    successful = 0
    failed = 0
    start_batch = args.start_batch

    for batch_num in range(start_batch, total_batches + 1):
        start_idx = (batch_num - 1) * batch_size
        end_idx = min(start_idx + batch_size, total_files)
        batch_files = all_files[start_idx:end_idx]

        if process_batch(batch_num, batch_files, total_batches):
            successful += 1
        else:
            failed += 1

            # Ask user if they want to continue on error
            response = input(f"\nContinue with next batch? [y/N]: ").strip().lower()
            if response not in ['y', 'yes']:
                print("Stopping batch processing.")
                break

        # Small delay between batches
        if batch_num < total_batches:
            time.sleep(1)

    # Now rebuild the vector index from all processed chunks
    print(f"\n{'='*60}")
    print("Building vector index from processed chunks...")
    print(f"{'='*60}")

    try:
        # Get total chunks
        con = get_sqlite_rw()
        total_chunks = con.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        print(f"Total chunks in database: {total_chunks:,}")

        # Trigger vector index rebuild
        print("Encoding embeddings and building FAISS index...")
        reindex(incremental=False)

        print("\n✓ Vector index rebuilt successfully!")

    except Exception as e:
        print(f"\n✗ Error building vector index: {e}")
        import traceback
        traceback.print_exc()

    # Summary
    print(f"\n{'='*60}")
    print("Batch Indexing Summary")
    print(f"{'='*60}")
    print(f"Total files: {total_files:,}")
    print(f"Batches processed successfully: {successful}/{total_batches}")
    if failed > 0:
        print(f"Batches failed: {failed}")
    print()

    if failed > 0:
        return 1

    # Q/A quality gate — runs Haiku grader against the fresh index
    print(f"\n{'='*60}")
    print("Running Q/A quality gate (Claude Haiku)...")
    print(f"{'='*60}")
    import subprocess
    qa_script = Path(__file__).parent / "rag_qa_agent.py"
    if qa_script.exists():
        qa_result = subprocess.run(
            [sys.executable, str(qa_script)],
            cwd=str(project_root),
        )
        if qa_result.returncode == 1:
            print("\n⚠  Q/A gate: FAILED — index quality below 90% threshold.")
            print("   Review the report in Vault/System/Logs/rag_qa/ before using this index.")
            return 1
        elif qa_result.returncode == 2:
            print("\n⚠  Q/A gate: Could not run (setup error — RAG unavailable or missing key).")
            print("   Run manually: python System/Scripts/rag_qa_agent.py")
    else:
        print(f"⚠  Q/A agent not found at {qa_script} — skipping quality gate.")

    return 0


if __name__ == '__main__':
    sys.exit(main())
