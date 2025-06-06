import json

def create_reminder_list(reminder_file):
    """
    Create a reminder list with 3 pre-allocated slots for each time period, save as a json file
    """
    reminder_list = {}
    for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]:
        reminder_list[day] = {
            "Morning": [None, None, None],
            "Afternoon": [None, None, None],
            "Evening": [None, None, None]
        }
    with open(reminder_file, "w") as f:
        json.dump(reminder_list, f)

def add_one_time_event(reminder_file, day, time, event):
    """
    Add a reminder to a specific day and time
    """
    # First read the current content
    with open(reminder_file, "r") as f:
        reminder_list = json.load(f)
    
    # Find the first None slot and replace it
    for i in range(3):
        if reminder_list[day][time][i] is None:
            reminder_list[day][time][i] = event
            break
    
    # Write back the updated content
    with open(reminder_file, "w") as f:
        json.dump(reminder_list, f)
    
    return reminder_list

def add_everyday_event(reminder_file, time, event):
    """
    Add a reminder to every day at a specific time
    """
    # First read the current content
    with open(reminder_file, "r") as f:
        reminder_list = json.load(f)
    
    for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]:
        # Find the first None slot and replace it
        for i in range(3):
            if reminder_list[day][time][i] is None:
                reminder_list[day][time][i] = event
                break
    
    # Write back the updated content
    with open(reminder_file, "w") as f:
        json.dump(reminder_list, f)
    
    return reminder_list

def get_event_from_date_time(reminder_file, day, time):
    """
    Get a reminder from a specific day and time
    """
    with open(reminder_file, "r") as f:
        reminder_list = json.load(f)
    return reminder_list[day][time]
    
def get_event_from_time(reminder_file, time):
    """
    Get all reminders from a specific time
    """
    with open(reminder_file, "r") as f:
        reminder_list = json.load(f)
    return reminder_list[time]

def get_event_from_day(reminder_file, day):
    """
    Get all reminders from a specific day
    """
    with open(reminder_file, "r") as f:
        reminder_list = json.load(f)
    return reminder_list[day]

def get_event_from_event(reminder_file, event):
    """
    Get all reminders from a specific event
    """
    with open(reminder_file, "r") as f:
        reminder_list = json.load(f)
    for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]:
        for time in ["Morning", "Afternoon", "Evening"]:
            if event in reminder_list[day][time]:
                return reminder_list[day][time]
    return None

def delete_event(reminder_file, date, time, event):
    """
    Delete a reminder from a specific day and time, reset to None
    """
    with open(reminder_file, "r") as f:
        reminder_list = json.load(f)
    index = reminder_list[date][time].index(event)
    reminder_list[date][time][index] = None
    # reorder the list
    reminder_list[date][time] = [x for x in reminder_list[date][time] if x is not None]
    with open(reminder_file, "w") as f:
        json.dump(reminder_list, f)
    return reminder_list

def user_input(reminder_file):
    """
    User input: first determine one time or everyday
    then determine the day and time
    then input the reminder
    Allow up to 3 retries for invalid inputs
    """
    def get_valid_input(prompt, valid_options, case_sensitive=False):
        for attempt in range(3):
            user_input = input(prompt)
            if not case_sensitive:
                user_input = user_input.capitalize()
                valid_options = [opt.capitalize() for opt in valid_options]
            if user_input in valid_options:
                return user_input
            print(f"Invalid input. Please try again. ({2-attempt} attempts remaining)")
        raise ValueError("Maximum retry attempts reached")

    try:
        one_time_or_everyday = get_valid_input(
            "Is this a one time reminder or an everyday reminder? (one time/everyday): ",
            ["one time", "everyday"],
            case_sensitive=False
        )

        if one_time_or_everyday == "one time":
            day = get_valid_input(
                "Enter the day: ",
                ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
                case_sensitive=False
            )
            time = get_valid_input(
                "Enter the time: ",
                ["Morning", "Afternoon", "Evening"],
                case_sensitive=False
            )
            reminder = input("Enter the reminder: ")
            add_one_time_event(reminder_file, day, time, reminder)
        else:  # everyday
            time = get_valid_input(
                "Enter the time: ",
                ["Morning", "Afternoon", "Evening"],
                case_sensitive=False
            )
            reminder = input("Enter the reminder: ")
            add_everyday_event(reminder_file, time, reminder)
    except ValueError as e:
        print(f"Error: {str(e)}")
        return

# should look like
"""
╔═══════════════╦═══════════════╦═══════════════╦═══════════════╦═══════════════╦═══════════════╦═══════════════╦═══════════════╗
║               ║    Monday     ║   Tuesday     ║   Wednesday   ║   Thursday    ║    Friday     ║   Saturday    ║    Sunday     ║
╠═══════════════╬═══════════════╬═══════════════╬═══════════════╬═══════════════╬═══════════════╬═══════════════╬═══════════════╣
║               ║    Event 1    ║   Event 2     ║               ║               ║               ║               ║               ║
║    Morning    ║    Event 4    ║               ║               ║               ║               ║               ║               ║
║               ║    Event 5    ║               ║               ║               ║               ║               ║               ║
╠═══════════════╬═══════════════╬═══════════════╬═══════════════╬═══════════════╬═══════════════╬═══════════════╬═══════════════╣
║               ║               ║               ║               ║    Event 3    ║               ║               ║               ║
║    Afternoon  ║               ║               ║               ║               ║               ║               ║               ║
║               ║               ║               ║               ║               ║               ║               ║               ║
╠═══════════════╬═══════════════╬═══════════════╬═══════════════╬═══════════════╬═══════════════╬═══════════════╬═══════════════╣
║               ║               ║               ║               ║               ║               ║               ║               ║
║    Evening    ║               ║               ║               ║               ║               ║               ║               ║
║               ║               ║               ║               ║               ║               ║               ║               ║
╚═══════════════╩═══════════════╩═══════════════╩═══════════════╩═══════════════╩═══════════════╩═══════════════╩═══════════════╝
"""

def print_reminder_list(reminder_file):
    """
    Print the reminder list in a formatted table with exactly 3 lines for each time slot
    """
    with open(reminder_file, "r") as f:
        reminder_list = json.load(f)
    # Define column widths and borders
    col_width = 20
    border = "═" * col_width
    top_border = "╔" + "╦".join([border] * 8) + "╗"
    middle_border = "╠" + "╬".join([border] * 8) + "╣"
    bottom_border = "╚" + "╩".join([border] * 8) + "╝"
    
    # Print header
    print(top_border)
    
    # Print days header
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    days_row = "║" + f"{'':^{col_width}}" + "║" + "║".join(f"{day:^{col_width}}" for day in days) + "║"
    print(days_row)
    print(middle_border)
    
    # Print each time slot
    for time in ['Morning', 'Afternoon', 'Evening']:
        # Print events for each day
        for line in range(3):
            event_row = "║" + f"{time if line == 1 else '':^{col_width}}" + "║"
            for day in days:
                events = reminder_list[day][time]
                if isinstance(events, list) and len(events) > line:
                    event = events[line]
                    event_str = '' if event is None else str(event)
                else:
                    event_str = ''
                event_row += f"{event_str:^{col_width}}" + "║"
            print(event_row)
        
        print(middle_border)
    
    print(bottom_border)

if __name__ == "__main__":
    reminder_file = "./UI/reminder_list.json"
    create_reminder_list(reminder_file)
    # testing: add multiple reminders
    add_one_time_event(reminder_file, "Monday", "Morning", "Event 1")
    add_one_time_event(reminder_file, "Monday", "Afternoon", "Event 2")
    add_everyday_event(reminder_file, "Afternoon", "Take medicine")
    add_everyday_event(reminder_file, "Evening", "Meet grandchild")

    user_input(reminder_file)
    print_reminder_list(reminder_file)
    delete_event(reminder_file, "Monday", "Morning", "Event 1")
    print_reminder_list(reminder_file)
