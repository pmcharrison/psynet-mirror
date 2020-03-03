from dlgr_utils.timeline import Page, InfoPage, Timeline, SuccessfulEndPage, ReactivePage, NAFCPage, CodeBlock, while_loop, join, GoTo, ReactiveGoTo
from datetime import datetime

Timeline(
    ReactivePage(            
        lambda experiment, participant: 
            InfoPage(f"The current time is {datetime.now().strftime('%H:%M:%S')}."),
        time_allotted=5
    ),
    CodeBlock(lambda experiment, participant: participant.set_answer("No")),
    while_loop(
        lambda experiment, participant: participant.answer == "No",
        NAFCPage(
            label="loop_nafc",
            prompt="Would you like to stay in this loop?",
            choices=["Yes", "No"],
            time_allotted=3
        )
    ),
    # NAFCPage(
    #     label="test_nafc",            
    #     prompt="What's your favourite colour?",
    #     choices=["Red", "Green", "Blue"],
    #     time_allotted=5
    # ),
    # CodeBlock(
    #     lambda experiment, participant:
    #         participant.set_var("favourite_colour", participant.answer)
    # ),
    # ReactivePage(
    #     lambda experiment, participant: 
    #         InfoPage(f"OK, your favourite colour is {participant.answer.lower()}."),
    #     time_allotted=3
    # ),
    SuccessfulEndPage()
)

# while_loop(
#     lambda experiment, participant: participant.answer == "No",
#     NAFCPage(
#         label="loop_nafc",
#         prompt="Would you like to stay in this loop?",
#         choices=["Yes", "No"],
#         time_allotted=3
#     )
# )
