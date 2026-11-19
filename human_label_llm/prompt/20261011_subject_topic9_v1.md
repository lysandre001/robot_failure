---
id: 20261011_subject_topic9_v1
version: "1.0.0"
date: 2026-10-11
purpose: |
  YouTube comments on robot-competition videos. Multi-label primary topic
  (nine categories). Compare with the human column 对象. A hit is any
  overlap between the model labels and the human labels.
description: |
  2026-10-11 YouTube subject topic, nine categories, multi-label.
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
  retry_hint: 'Output only JSON: {"labels": ["Exact category name"], "note": "brief rationale"}'
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
Select one or more categories per comment. If a comment addresses multiple distinct topics, assign all applicable categories.
If a clear topic falls outside the categories, use No Clear Subject and suggest a new topic label in note.

# INPUT
<comment>{comment}</comment>

# OUTPUT
Return only valid JSON (no markdown fences):
{{"labels": ["Robot", "Self"], "note": "The comment evaluates the robot’s performance and compares it with the commenter’s own abilities."}}
