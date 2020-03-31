============
The timeline
============

The timeline determines the sequential logic of the experiment.
A timeline comprises a series of *test elements* that are ordinarily
presented sequentially. There are three main kinds of test elements:

* `Pages`_
* `Reactive pages`_
* `Code blocks`_

`Pages`_ define the web page that is shown to the participant at a given 
point in time, and have fixed content that is the same for all participants.
`Reactive pages`_ are like pages, but include content that is computed
when the participant's web page loads.
`Code blocks`_ contain server logic that is executed in between pages, 
for example to assign the participant to a group or to save the participant's data.

All these test elements are defined as `dlgr_utils` classes inheriting from
`Elt`, the generic test element object.
Pages correspond to the `Page` class;
reactive pages correspond to the `ReactivePage` class;
code blocks correspond to the `CodeBlock` class.
These different test elements may be created using their constructor functions, e.g.:

::

    from dlgr_utils.timeline import CodeBlock

    CodeBlock(lambda participant, experiment: participant.var.score = 50)


Pages
-----

Pages are defined in a hierarchy of object-oriented classes. The base class 
is `Page`, which provides the most general and verbose way to specify a `dlgr_utils` page.
A simpler example is `InfoPage`, which takes a piece of text or HTML and displays it to the user:

::

    from dlgr_utils.timeline import InfoPage

    InfoPage("Welcome to the experiment!")

More complex pages might solicit a response from the user,
for example in the form of a text-input field:

::

    from dlgr_utils.timeline import TextInputPage

    TextInputPage(
        "full_name",
        "Please enter your full name",
        time_allotted=5,
        one_line=True
    )

or in a multiple-choice format:

::

    from dlgr_utils.timeline import NAFCPage

    NAFCPage(
        label="chocolate",
        prompt="Do you like chocolate?",
        choices=["Yes", "No"],
        time_allotted=3
    )

See the documentation for individual classes for more guidance, for example:

* Page
* InfoPage
* TextInputPage
* NumberInputPage
* NAFCPage

Often you may wish to create a custom page type. The best way is usually
to start with the source code for a related page type from the `dlgr_utils`
package, and modify it to make your new page type. These page types
should usually inherit from the most specific relevant `dlgr_utils` page type;
for example, `NumberInputPage` inherits from `TextInputPage`, 
and adds a validation step to make sure that the user has entered a valid number.

We hope to significantly extend the page types available in `dlgr_utils` in the future.
When you've found a custom page type useful for your own experiment,
you might consider submitting it to the `dlgr_utils` code base via 
a Pull Request (or, in GitLab terminology, a Merge Request).

This should be enough to start experimenting with different kinds of page types.
For a full understanding of the customisation possibilities, see 
the Page class documentation.

Reactive pages
--------------

Code blocks
-----------

Allotted time
-------------

Control logic
-------------
