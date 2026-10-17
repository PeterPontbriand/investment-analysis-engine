# Revision directory

`0001_persistence` creates the five Gate D0-approved application tables and
encoding-version seed. It is the B3 implementation, pending Gate B review.
The earlier B2 bootstrap had no revisions. Keep historical revisions independent
of mutable application metadata so a future schema edit cannot change replay.
