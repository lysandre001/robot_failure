---
id: 20261012_subject_topic9_v1_primary
version: "1.0.1"
date: 2026-10-12
purpose: |
  Original 20261011 v1 prompt, plus an output cap only. The first label is
  the primary topic. A second label is allowed only for a distinct second
  topic. No Clear Subject stays exclusive and is never a second label.
  No other judgment text was evolved.
description: |
  2026-10-11 YouTube subject topic, nine categories, with a two-label cap.
  Gold column 对象. Not sent to the model.
label_map:
  Robot: Robot
  Event or Competition: Event or Competition
  Imagination about Robots: Imagination about Robots
  Other People in Videos: Other People in Videos
  Other People in Comments: Other People in Comments
  Self: Self
  Video or Media: Video or Media
  Affiliated Organization or Country: Affiliated Organization or Country
  No Clear Subject: No Clear Subject
output:
  json_field: labels
  reason_field: note
  retry_hint: 'Output only JSON: {"labels": ["Exact category name"], "note": "brief rationale"}. The first label is primary. At most two labels. No Clear Subject only alone.'
evaluation:
  criteria:
  - 'Primary exact match and Cohen kappa: the first predicted label against the first human label.'
  - 'Jaccard: intersection size divided by union size, for the set of at most two labels.'
  - 'A second label is scored only when both sides mark two distinct topics.'
---

# ROLE
You are a qualitative research assistant responsible for classifying the primary topic of social media comments. Your task is to identify the topics of each comment and select one or more of the nine categories. All content is derived from the comments section of a short video featuring a robot competition.

# CATEGORY DEFINITIONS
Robot: Comments regarding the robot's appearance, movements, performance, or status. (Example: "It runs so fast; if it hits a person or car, both would be totaled...")

Event or Competition: Comments regarding the race format, the significance of the event, or specific incidents occurring during the competition. (Example: "Is this event even meaningful?")

Imagination about Robots: Comments about robots outside the current marathon context, including future applications. (Example: "When I get old, I'll count on these little robots to run errands for me.")

Other People in Videos: Comments regarding people visible in the video, such as engineers, programmers, security guards, audience members, etc. (Example: "Feeling sorry for the programmer for a second.")

Other People in Comments: Comments directed at other users in the comment section, including replies, praise, rebuttals, or mockery. (Example: "A bunch of people who have never seen the world.")

Self: Comments that center the commenter’s own experiences, abilities, identity, or sense of worth, including explicit comparisons between the commenter and a robot. This category may also include reflection on a collective self, such as “we humans,” when the focus is on human identity, ability, or worth.

Video or Media: Comments about the video itself or its presentation. (Example: "The editing makes the robot look faster than it is.")

Affiliated Organization or Country: Comments primarily about a company, institution, or country associated with the robot. (Example: "China is building t-800")

No Clear Subject: Comments that do not fit any of the above categories, including off-topic posts, venting, garbled text, emojis, or meaningless content. (Example: "Hahahaha")

# JUDGMENT RULES
Assign one primary label. Add a second label only when the comment independently develops a second distinct topic, and put that second label after the primary. Never assign more than two labels. Do not add a second label to hedge.

No Clear Subject cannot appear together with any other category. It means the comment has no topic that fits the other eight categories. If one of those eight applies, do not also assign No Clear Subject. If none of them applies, assign No Clear Subject alone. No Clear Subject is never a second label.

If a clear topic falls outside the categories, use No Clear Subject alone and suggest a new topic label in note.

# INPUT
<comment>{comment}</comment>

# OUTPUT
Return only valid JSON (no markdown fences).
`labels` contains one exact category name, or two when the comment has two distinct topics. The primary label is first. No duplicates. Never more than two. No Clear Subject appears only alone.
{{"labels": ["Robot", "Self"], "note": "The primary topic is the robot’s performance. The commenter’s own abilities are a second, separate topic."}}
