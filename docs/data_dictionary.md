# CRICKET 360 — Data Dictionary

## Core Tables

### dim_player
Master player dimension containing player identity and enriched profile information.

Key fields:
- player_id
- display_name
- full_name
- country
- date_of_birth
- role
- batting_style
- bowling_style
- career_start
- career_end
- photo_url

### matches
Match-level information.

Key fields:
- match_id
- match_date
- format
- season
- team1
- team2
- venue
- city
- event_name

### ball_by_ball
Delivery-level cricket dataset used as the foundation for statistical aggregation.

Contains more than 11.5 million delivery records.

### player_match_batting
Player batting performance at match level.

Key metrics:
- Runs
- Balls_Faced
- Fours
- Sixes
- Strike_Rate
- Dismissals
- Not_Out

### player_match_bowling
Player bowling performance at match level.

Key metrics:
- runs_conceded
- legal_balls
- wickets
- Economy
- Bowling_Strike_Rate
- extras_conceded

### player_career_by_format
Career statistics grouped by player and cricket format.

### player_by_season
Player performance grouped by season.

### player_vs_team
Player performance analysis by opposition.

### player_vs_tournament
Player performance grouped by tournament.

### batter_vs_bowler
Batter-vs-bowler matchup statistics.

### batting_form_trend
Match-level batting form and performance trends.

### bowling_form_trend
Match-level bowling form and performance trends.

### team_summary
Aggregated team-level statistics.

### team_vs_tournament
Team performance across tournaments.

### head_to_head_summary
Team-vs-team historical matchup statistics.

### tournament_summary
Tournament-level aggregated statistics.

### season_summary
Season-level analytical summary.

### venue_summary
Venue-level analytical summary.

### format_summary
Statistics grouped by cricket format.

## Data Model Philosophy

CRICKET 360 uses pre-aggregated analytical tables to reduce repeated calculations inside Power BI and provide responsive dashboard interactions while retaining the detailed ball-by-ball dataset as the analytical foundation.
