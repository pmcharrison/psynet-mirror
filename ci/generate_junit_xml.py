#!/usr/bin/env python
"""
A python script that takes a text file from standard input and
outputs a junit XML file containing that file as summary.
--classname and --testname are optional arguments that can be passed.
It uses `click` to get user arguments.
"""
import click

JUNIT_TEMPLATE = """
<testcase classname="{classname}" name="{testname}">
    <system-out>
        <![CDATA[
            {text}
        ]]>
    </system-out>
</testcase>
"""


@click.command()
@click.option('--classname', default='', help='The classname of the test')
@click.option('--testname', default='', help='The name of the test')
def main(classname, testname):
    text = click.get_text_stream('stdin').read()
    junit_xml = JUNIT_TEMPLATE.format(
        classname=classname,
        testname=testname,
        text=text
    )
    click.get_text_stream('stdout').write(junit_xml)


if __name__ == '__main__':
    main()
