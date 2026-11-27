"""Asking while unsure: what an asking is worth, a record of one's own askings, how sure to be, whom to trust, an
asking made only so often, what an inquiry is promised, a judgement of the answer taken and an asking that takes
time (§76.13 to §76.21).

What an asking is worth is read from recorded askings: where it was asked, how sure the best answer was there,
where it led and how sure the best answer was then (``Askings``). Under a charge for an asking, a share of what a
right answer is worth, the worth of each asking at each place follows from the last places backwards (``Worth``).
``Unsure`` is the concept that holds an inquiry's answers and, beside them, the open asking worth most with that
worth as its chance, so the frame's own rule decides between answering and asking, and which to ask. Each asking
may be charged its own share, so askings that different experts serve at different costs are weighed in the one
rule (§76.15). The record need not be given: ``Learning`` begins with whatever record it is handed, an empty one
too, and ``Unsure`` keeps it by the askings the frame itself makes, each asking tried a stated number of times
where it stands (§76.14). The same askings say whether the stated chances are right, since a right chance of the
answer held does not drift when more is learned: ``Sureness`` reads from them, with no word on what was right, how
far too sure or too modest the chances are (§76.16). Where an inquiry says what each of its sources said, and one
source is taken as naming what was right, ``Trust`` makes the chances from those words and learns from the names
how far each source is to be believed (§76.17). An asking that may be made only so often is kept to its limit by
a price added to its charge where the rule weighs it (§76.18). ``Promise`` keeps what inquiries were promised
against what they came to hold, which says how far a record promises too much (§76.19). Where all that comes
back is whether the answer given was paid, the record keeps the share paid of the answers given at each place
and values answering there by it (§76.20); and an inquiry that ended while an asking was being served is recorded
as led to ``OVER``, so that what waiting costs is counted with everything else (§76.21).

The frame these are concepts of is ``nca.thinking``. Nothing here says what a place or an asking stands for, who
serves an asking, or what is being found out.
"""
from nca.asking.readings import Promise, Sureness, Trust
from nca.asking.record import OVER, Askings, Inquiry, Standing, Worth
from nca.asking.unsure import Learning, Unsure

__all__ = ["OVER", "Askings", "Inquiry", "Learning", "Promise", "Standing", "Sureness", "Trust", "Unsure", "Worth"]
