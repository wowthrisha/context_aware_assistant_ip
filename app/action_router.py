class ActionRouter:

    reminders = []

    def handle_action(self, intent, user_input):

        if intent == "set_reminder":

            reminder = {
                "task": user_input,
                "time": "parsed_later"   # MVP placeholder
            }

            self.reminders.append(reminder)
            return reminder   # return JSON instead of text

        elif intent == "save_habit":
            return {"status": "habit_saved"}

        elif intent == "save_preference":
            return {"status": "preference_saved"}

        return None