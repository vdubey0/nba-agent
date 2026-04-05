"""
Script to delete games from 03/25/2025 to 04/01/2025 that were accidentally added.
This will also delete related team_game_stats and player_game_stats records.
"""
from datetime import date
from sqlalchemy.orm import Session
from app.db import SessionLocal, engine
from app.models.game import Game
from app.models.team_game_stats import TeamGameStats
from app.models.player_game_stats import PlayerGameStats

def delete_games_in_date_range(start_date: date, end_date: date):
    """
    Delete games and their related stats within the specified date range.
    
    Args:
        start_date: Start date (inclusive)
        end_date: End date (inclusive)
    """
    db: Session = SessionLocal()
    
    try:
        # Find games in the date range
        games_to_delete = db.query(Game).filter(
            Game.game_date >= start_date,
            Game.game_date <= end_date
        ).all()
        
        if not games_to_delete:
            print(f"No games found between {start_date} and {end_date}")
            return
        
        game_ids = [game.game_id for game in games_to_delete]
        print(f"\nFound {len(games_to_delete)} games to delete:")
        for game in games_to_delete:
            print(f"  - Game ID: {game.game_id}, Date: {game.game_date}, Season: {game.season}")
        
        # Count related records
        team_stats_count = db.query(TeamGameStats).filter(
            TeamGameStats.game_id.in_(game_ids)
        ).count()
        
        player_stats_count = db.query(PlayerGameStats).filter(
            PlayerGameStats.game_id.in_(game_ids)
        ).count()
        
        print(f"\nRelated records to delete:")
        print(f"  - Team game stats: {team_stats_count}")
        print(f"  - Player game stats: {player_stats_count}")
        
        # Ask for confirmation
        response = input("\nDo you want to proceed with deletion? (yes/no): ")
        if response.lower() != 'yes':
            print("Deletion cancelled.")
            return
        
        # Delete related records first (due to foreign key constraints)
        print("\nDeleting player game stats...")
        deleted_player_stats = db.query(PlayerGameStats).filter(
            PlayerGameStats.game_id.in_(game_ids)
        ).delete(synchronize_session=False)
        print(f"Deleted {deleted_player_stats} player game stats records")
        
        print("Deleting team game stats...")
        deleted_team_stats = db.query(TeamGameStats).filter(
            TeamGameStats.game_id.in_(game_ids)
        ).delete(synchronize_session=False)
        print(f"Deleted {deleted_team_stats} team game stats records")
        
        print("Deleting games...")
        deleted_games = db.query(Game).filter(
            Game.game_date >= start_date,
            Game.game_date <= end_date
        ).delete(synchronize_session=False)
        print(f"Deleted {deleted_games} games")
        
        # Commit the transaction
        db.commit()
        print("\n✅ Deletion completed successfully!")
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ Error occurred: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    # Define the date range to delete
    start_date = date(2025, 3, 24)
    end_date = date(2025, 4, 2)
    
    print("=" * 60)
    print("NBA Games Deletion Script")
    print("=" * 60)
    print(f"Date range: {start_date} to {end_date}")
    print("=" * 60)
    
    delete_games_in_date_range(start_date, end_date)

# Made with Bob
