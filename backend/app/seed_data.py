"""Seed script to populate database with test data for local development."""

import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from sqlmodel import SQLModel, select, func
from sqlmodel.ext.asyncio.session import AsyncSession
from app.database import engine, get_session
from app.db.items import create_item
from app.models.item import ItemCreate
from app.models.learner import Learner
from app.models.interaction import InteractionLog


async def seed_database():
    """Populate database with sample data for testing."""
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    
    async with AsyncSession(engine) as session:
        # Create sample items (labs and tasks)
        sample_items = [
            # Lab 1: Python Basics
            {"type": "lab", "title": "lab-1", "description": "Python Basics"},
            {"type": "task", "parent_id": 1, "title": "task-1-1", "description": "Variables and Types"},
            {"type": "task", "parent_id": 1, "title": "task-1-2", "description": "Control Flow"},
            
            # Lab 2: Data Structures
            {"type": "lab", "title": "lab-2", "description": "Data Structures"},
            {"type": "task", "parent_id": 4, "title": "task-2-1", "description": "Lists and Tuples"},
            {"type": "task", "parent_id": 4, "title": "task-2-2", "description": "Dictionaries"},
            
            # Lab 3: Functions
            {"type": "lab", "title": "lab-3", "description": "Functions"},
            {"type": "task", "parent_id": 7, "title": "task-3-1", "description": "Defining Functions"},
            {"type": "task", "parent_id": 7, "title": "task-3-2", "description": "Lambda Functions"},
            
            # Lab 6: Software Engineering
            {"type": "lab", "title": "lab-6", "description": "Software Engineering Toolkit"},
            {"type": "task", "parent_id": 10, "title": "task-6-1", "description": "Agent Setup"},
            {"type": "task", "parent_id": 10, "title": "task-6-2", "description": "Documentation Agent"},
            {"type": "task", "parent_id": 10, "title": "task-6-3", "description": "System Agent"},
        ]
        
        print("Seeding items...")
        for item_data in sample_items:
            try:
                item = ItemCreate(
                    type=item_data["type"],
                    parent_id=item_data.get("parent_id"),
                    title=item_data["title"],
                    description=item_data["description"],
                )
                create_item(session, item)
                print(f"  Created: {item_data['title']}")
            except Exception as e:
                print(f"  Skip (may exist): {item_data['title']} - {e}")
        
        # Create sample learners
        print("\nSeeding learners...")
        sample_learners = [
            Learner(external_id="student-001", student_group="CS-2024"),
            Learner(external_id="student-002", student_group="CS-2024"),
            Learner(external_id="student-003", student_group="CS-2024"),
        ]
        
        for learner in sample_learners:
            try:
                session.add(learner)
                print(f"  Created: {learner.external_id}")
            except Exception as e:
                print(f"  Skip: {learner.external_id} - {e}")
        
        await session.commit()
        print("  Learners created!")

        # Create sample interactions
        print("\nSeeding interactions...")
        import random
        from datetime import datetime, timedelta

        base_time = datetime.now() - timedelta(days=7)

        for i, learner in enumerate(sample_learners):
            for item_id in range(1, 13):  # Items 1-12
                # Random interaction
                if random.random() > 0.3:  # 70% chance of interaction
                    interaction = InteractionLog(
                        learner_id=learner.id,
                        item_id=item_id,
                        kind="check",
                        score=random.uniform(0.5, 1.0),
                        checks_passed=random.randint(3, 10),
                        checks_total=10,
                        created_at=base_time + timedelta(hours=i*24 + item_id),
                    )
                    session.add(interaction)

        await session.commit()
        print("  Interactions created!")

        print("\n✓ Database seeded successfully!")


async def main():
    await seed_database()


if __name__ == "__main__":
    asyncio.run(main())
