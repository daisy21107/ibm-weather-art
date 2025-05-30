def create_reminder_list():
    """
    Create a reminder list with 3 pre-allocated slots for each time period
    """
    reminder_list = {}
    for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]:
        reminder_list[day] = {
            "Morning": [None, None, None],
            "Afternoon": [None, None, None],
            "Evening": [None, None, None]
        }
    return reminder_list

def add_one_time_reminder(reminder_list, day, time, reminder):
    """
    Add a reminder to a specific day and time
    """
    # Find the first None slot and replace it
    for i in range(3):
        if reminder_list[day][time][i] is None:
            reminder_list[day][time][i] = reminder
            break
    return reminder_list

def add_everyday_reminder(reminder_list, time, reminder):
    """
    Add a reminder to every day at a specific time
    """
    for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]:
        # Find the first None slot and replace it
        for i in range(3):
            if reminder_list[day][time][i] is None:
                reminder_list[day][time][i] = reminder
                break
    return reminder_list

def get_reminder_from_date_time(reminder_list, day, time):
    """
    Get a reminder from a specific day and time
    """
    return reminder_list[day][time]
    
def get_reminder_from_time(reminder_list, time):
    """
    Get all reminders from a specific time
    """
    return reminder_list[time]

def get_reminder_from_day(reminder_list, day):
    """
    Get all reminders from a specific day
    """
    return reminder_list[day]

def get_reminder_from_event(reminder_list, event):
    """
    Get all reminders from a specific event
    """
    for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]:
        for time in ["Morning", "Afternoon", "Evening"]:
            if event in reminder_list[day][time]:
                return reminder_list[day][time]
    return None

def delete_reminder(reminder_list, date, time, event):
    """
    Delete a reminder from a specific day and time, reset to None
    """
    index = reminder_list[date][time].index(event)
    reminder_list[date][time][index] = None
    # reorder the list
    reminder_list[date][time] = [x for x in reminder_list[date][time] if x is not None]
    return reminder_list

# user input: first determine one time or everyday
# then determine the day and time
# then input the reminder
def user_input():
    """
    User input: first determine one time or everyday
    then determine the day and time
    then input the reminder
    """
    one_time_or_everyday = input("Is this a one time reminder or an everyday reminder? (one time/everyday): ")
    if one_time_or_everyday == "one time":
        day = input("Enter the day: ")
        assert day in ["Monday", "monday", "Tuesday", "tuesday", "Wednesday", "wednesday", "Thursday", "thursday", "Friday", "friday", "Saturday", "saturday", "Sunday", "sunday"]
        # not sensitive to case
        day = day.capitalize()
        time = input("Enter the time: ")
        assert time in ["Morning", "morning", "Afternoon", "afternoon", "Evening", "evening"]
        time = time.capitalize()
        reminder = input("Enter the reminder: ")
        add_one_time_reminder(reminder_list, day, time, reminder)
    elif one_time_or_everyday == "everyday":
        time = input("Enter the time: ")
        assert time in ["Morning", "morning", "Afternoon", "afternoon", "Evening", "evening"]
        time = time.capitalize()
        reminder = input("Enter the reminder: ")
        add_everyday_reminder(reminder_list, time, reminder)
    else:
        raise ValueError("Invalid input")

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

def print_reminder_list(reminder_list):
    """
    Print the reminder list in a formatted table with exactly 3 lines for each time slot
    """
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
    reminder_list = create_reminder_list()
    # testing: add multiple reminders
    reminder_list = add_one_time_reminder(reminder_list, "Monday", "Morning", "Event 1")
    reminder_list = add_one_time_reminder(reminder_list, "Monday", "Afternoon", "Event 2")
    reminder_list = add_one_time_reminder(reminder_list, "Monday", "Evening", "Event 3")
    reminder_list = add_everyday_reminder(reminder_list, "Morning", "Event 4")
    reminder_list = add_everyday_reminder(reminder_list, "Afternoon", "Take medicine")
    reminder_list = add_everyday_reminder(reminder_list, "Evening", "Meet grandchild")


    user_input()
    print_reminder_list(reminder_list)
    reminder_list = delete_reminder(reminder_list, "Monday", "Morning", "Event 1")
    print_reminder_list(reminder_list)
